# -*- coding: utf-8 -*-
"""Tempo — spectral-flux onset envelope + autocorrelation, octave-ambiguity aware."""
from typing import List

import numpy as np

from ..dsp import stft_mag
from ..evidence import Evidence, Finding, FACT, HYPOTHESIS

BPM_RANGE = (55.0, 200.0)


def _onset_envelope(x: np.ndarray, sr: int) -> np.ndarray:
    spec = stft_mag(x, sr, frame_ms=40.0, hop_ms=10.0)
    flux = np.diff(spec, axis=0)
    flux[flux < 0] = 0.0
    env = flux.sum(axis=1)
    if len(env) == 0:
        return np.zeros(1)
    env = (env - env.mean()) / (env.std() + 1e-9)
    return env


def _autocorr_peaks(env: np.ndarray, sr_env: float) -> List[tuple]:
    env = env - env.mean()
    ac = np.correlate(env, env, mode="full")[len(env) - 1:]
    ac /= (ac[0] + 1e-12)
    lag_min = int(60.0 / BPM_RANGE[1] * sr_env)
    lag_max = int(60.0 / BPM_RANGE[0] * sr_env)
    lag_max = min(lag_max, len(ac) - 2)
    peaks = []
    for lag in range(lag_min + 1, lag_max):
        if ac[lag] > ac[lag - 1] and ac[lag] >= ac[lag + 1] and ac[lag] > 0:
            # parabolic refinement on lag
            denom = ac[lag - 1] - 2 * ac[lag] + ac[lag + 1]
            shift = 0.5 * (ac[lag - 1] - ac[lag + 1]) / (denom + 1e-12) if denom != 0 else 0.0
            refined = lag + np.clip(shift, -1, 1)
            bpm = 60.0 * sr_env / refined
            if BPM_RANGE[0] <= bpm <= BPM_RANGE[1]:
                peaks.append((float(bpm), float(ac[lag])))
    peaks.sort(key=lambda p: -p[1])
    return peaks[:6]


def analyze(x: np.ndarray, sr: int) -> Finding:
    sr_env = 100.0  # 10 ms hop
    env = _onset_envelope(x, sr)
    peaks = _autocorr_peaks(env, sr_env)

    if not peaks:
        return Finding(id="tempo", title="Tempo", status="UNKNOWN", confidence=0.0,
                       conclusion="No stable rhythmic pulse found (ambient/free material?)",
                       caveats=["Autocorrelation of onset envelope found no peak above noise."])

    best_bpm, best_score = peaks[0]
    # octave ambiguity: is half / double tempo nearly as strong?
    half = next((p for p in peaks[1:] if abs(p[0] * 2 - best_bpm) < 3.0), None)
    dbl = next((p for p in peaks[1:] if abs(p[0] / 2 - best_bpm) < 3.0), None)
    ambiguous = (half and half[1] > 0.85 * best_score) or (dbl and dbl[1] > 0.85 * best_score)

    if ambiguous:
        alt = half[0] if half else (dbl[0] if dbl else best_bpm)
        f = Finding(id="tempo", title="Tempo & feel", status=HYPOTHESIS,
                    confidence=min(0.9, 0.4 + best_score),
                    conclusion="~{} BPM, but {} BPM is nearly as strong — trust your feet, "
                               "the pulse grid is octave-ambiguous".format(round(best_bpm, 1), round(alt, 1)))
    else:
        f = Finding(id="tempo", title="Tempo & feel", status=FACT,
                    confidence=min(1.0, 0.5 + best_score),
                    conclusion="{} BPM".format(round(best_bpm, 1)))

    f.add(Evidence("autocorrelation peak BPM", round(best_bpm, 2), "BPM",
                   detail="peak strength {:.2f}".format(best_score)))
    f.add(Evidence("candidate peaks", [round(p[0], 1) for p in peaks[:4]], "BPM",
                   detail="sorted by autocorrelation strength"))
    f.add(Evidence("onset envelope std", round(float(env.std()), 3), "",
                   detail="rhythmic clarity proxy; near 1.0 after normalization means clear transients"))
    return f
