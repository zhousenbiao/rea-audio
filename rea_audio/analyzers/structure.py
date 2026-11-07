# -*- coding: utf-8 -*-
"""Song structure — novelty-based segmentation. Output is HYPOTHESIS by nature."""
from typing import List

import numpy as np

from ..dsp import stft_mag
from ..evidence import Evidence, Finding, HYPOTHESIS
from .key_chords import chromagram


def _mmsec(t: float) -> str:
    return "{:d}:{:02d}".format(int(t // 60), int(t % 60))


def analyze(x: np.ndarray, sr: int) -> Finding:
    hop_s = 0.2
    win_s = 1.0
    chroma = chromagram(x, sr, hop_ms=hop_s * 1000)
    frame_len = int(sr * 0.04)
    spec = stft_mag(x, sr, frame_ms=40.0, hop_ms=hop_s * 1000)
    n = min(len(chroma), len(spec))
    if n < 12:
        return Finding(id="structure", title="Song structure", status="UNKNOWN", confidence=0.0,
                       conclusion="Track too short to segment")
    feats = np.hstack([chroma[:n], np.log1p(spec[:n, : min(spec.shape[1], 200)])])
    feats = (feats - feats.mean(axis=0)) / (feats.std(axis=0) + 1e-9)

    w = max(2, int(win_s / hop_s))
    novelty = []
    for i in range(w, n - w):
        before = feats[i - w:i].mean(axis=0)
        after = feats[i:i + w].mean(axis=0)
        novelty.append(float(np.linalg.norm(after - before)))
    novelty = np.array(novelty)
    if len(novelty) < 5:
        return Finding(id="structure", title="Song structure", status="UNKNOWN", confidence=0.0,
                       conclusion="Not enough timeline to segment")
    thr = novelty.mean() + 0.7 * novelty.std()
    boundary_frames = []
    for i in range(1, len(novelty) - 1):
        if novelty[i] > thr and novelty[i] >= novelty[i - 1] and novelty[i] > novelty[i + 1]:
            if not boundary_frames or i - boundary_frames[-1] > int(8.0 / hop_s):  # >=8 s apart
                boundary_frames.append(i)
    times = [(i + w) * hop_s for i in boundary_frames]

    # name segments by loudness relative to track median
    rms = np.sqrt((spec[:n] ** 2).mean(axis=1))
    med = np.median(rms)
    bounds = [0.0] + times + [n * hop_s]
    segments: List[str] = []
    for i in range(len(bounds) - 1):
        t0, t1 = bounds[i], bounds[i + 1]
        r = float(rms[int(t0 / hop_s):int(t1 / hop_s) + 1].mean())
        if r < 0.55 * med:
            label = "quiet/breakdown"
        elif r > 1.35 * med:
            label = "loud/full"
        else:
            label = "mid energy"
        segments.append("{}–{} {}".format(_mmsec(t0), _mmsec(t1), label))

    f = Finding(
        id="structure", title="Song structure", status=HYPOTHESIS, confidence=0.55,
        conclusion="{} sections: {}".format(len(segments), " | ".join(segments[:10])),
    )
    f.add(Evidence("novelty boundaries", ["{:.1f}s".format(t) for t in times[:12]],
                   detail="chroma+spectral change points, min spacing 8 s"))
    f.add(Evidence("section count", len(segments)))
    f.caveats.append("Section labels are energy-based guesses; a human would also use lyrics/instrumentation.")
    return f
