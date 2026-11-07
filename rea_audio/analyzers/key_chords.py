# -*- coding: utf-8 -*-
"""Key & chord progression — chroma folding, Krumhansl-Schmuckler profiles, chord templates."""
from typing import List, Tuple

import numpy as np

from ..dsp import stft_mag, freqs_of
from ..evidence import Evidence, Finding, FACT, HYPOTHESIS

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Kessler key profiles (major, minor), starting at tonic.
_KK_MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_KK_MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Chord templates over chroma (12,) binary/masked weights.
_CHORD_TEMPLATES = {
    "maj":  [1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0],
    "min":  [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0],
    "7":    [1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0],
    "maj7": [1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1],
    "min7": [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1],
    "dim":  [1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0],
    "sus4": [1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0],
}


def chromagram(x: np.ndarray, sr: int, hop_ms: float = 20.0) -> np.ndarray:
    """(n_frames, 12) energy-weighted chroma from an STFT, 60 Hz–5 kHz band only.

    Uses a long (~180 ms) window: at 40 ms the FFT resolution (~25 Hz) cannot
    separate neighbouring semitones in the bass (a semitone at 130 Hz is ~8 Hz),
    which smears energy across wrong pitch classes.
    """
    frame_ms = 180.0
    frame_len = int(sr * frame_ms / 1000.0)
    spec = stft_mag(x, sr, frame_ms=frame_ms, hop_ms=hop_ms)
    freqs = freqs_of(spec.shape[1], sr, frame_len)
    band = (freqs >= 60.0) & (freqs <= 5000.0)
    spec = spec[:, band]
    freqs = freqs[band]
    # whiten: subtract the per-frame median floor so broadband noise/click tails
    # stop diluting the harmonic content
    spec = np.maximum(spec - np.median(spec, axis=1, keepdims=True), 0.0)
    midi = np.round(12.0 * np.log2(np.maximum(freqs, 1e-6) / 440.0) + 69.0).astype(int)
    pitch_class = np.mod(midi, 12)
    chroma = np.zeros((spec.shape[0], 12))
    for pc in range(12):
        chroma[:, pc] = np.sqrt(spec[:, pitch_class == pc]).sum(axis=1)  # sqrt = mild power compression
    total = chroma.sum(axis=1, keepdims=True)
    chroma = chroma / (total + 1e-9)
    return chroma


def _key_from_chroma(global_chroma: np.ndarray) -> List[Tuple[str, float]]:
    scores = []
    for tonic in range(12):
        rotated = np.roll(global_chroma, -tonic)
        for mode, prof in (("major", _KK_MAJ), ("minor", _KK_MIN)):
            r = np.corrcoef(rotated, prof)[0, 1]
            scores.append(("{} {}".format(NOTE_NAMES[tonic], mode), float(r)))
    scores.sort(key=lambda s: -s[1])
    return scores


def _chord_of(chroma_bar: np.ndarray) -> Tuple[str, float]:
    best, best_score = "N.C.", -2.0
    for quality, template in _CHORD_TEMPLATES.items():
        tpl = np.array(template, dtype=float)
        for root in range(12):
            rot = np.roll(tpl, root)
            score = float(np.corrcoef(chroma_bar, rot)[0, 1])
            if score > best_score:
                best_score = score
                best = NOTE_NAMES[root] + ("" if quality == "maj" else quality)
    return best, best_score


def analyze(x: np.ndarray, sr: int, bpm: float = 0.0) -> Finding:
    chroma = chromagram(x, sr)
    active = chroma[chroma.sum(axis=1) > 1e-4]
    if len(active) < 10:
        return Finding(id="key", title="Key & chords", status="UNKNOWN", confidence=0.0,
                       conclusion="Almost no harmonic content in the 80 Hz–5 kHz band")
    global_chroma = active.mean(axis=0)
    scores = _key_from_chroma(global_chroma)
    best_key, best_r = scores[0]
    runner = scores[1]

    # Chord per bar if we have a tempo; otherwise per 2 s.
    bar_sec = (60.0 / bpm * 4.0) if bpm and bpm > 40 else 2.0
    frames_per_bar = max(1, int(bar_sec / 0.02))
    progression = []
    for start in range(0, len(active), frames_per_bar):
        bar = active[start:start + frames_per_bar].mean(axis=0)
        name, score = _chord_of(bar)
        t0 = start * 0.02
        if score > 0.5:
            progression.append((t0, name))

    # compress repeated bars -> progression string
    seq = []
    for _, name in progression:
        if not seq or seq[-1][0] != name:
            seq.append([name, 1])
        else:
            seq[-1][1] += 1
    prog_str = " – ".join("{}{}".format(n, "×{}".format(c) if c > 1 else "") for n, c in seq[:16])

    confidence = min(1.0, max(0.0, best_r))
    status = FACT if best_r > 0.8 else HYPOTHESIS
    conclusion = "Key: {}".format(best_key)
    if prog_str:
        conclusion += "; progression: {}".format(prog_str if len(prog_str) < 160 else prog_str[:157] + "...")

    f = Finding(id="key", title="Key & chords", status=status, confidence=confidence,
                conclusion=conclusion)
    f.add(Evidence("key correlation", round(best_r, 3), "r",
                   detail="Krumhansl-Schmuckler profile match"))
    f.add(Evidence("runner-up keys", [s[0] for s in scores[1:4]], "",
                   detail="r = {}; a close runner-up means the material is modally ambiguous".format(
                       round(runner[1], 3))))
    f.add(Evidence("global chroma (C..B)", [round(float(v), 3) for v in global_chroma], "energy",
                   snapshot=[float(v) for v in global_chroma], labels=list(NOTE_NAMES)))
    if bar_sec:
        f.add(Evidence("chord grid", round(bar_sec, 2), "s/bar", detail="4 beats @ analyzed tempo"))
    if best_r < 0.6:
        f.caveats.append("Key correlation is weak; chromatic/atonal material or noisy mix.")
    return f
