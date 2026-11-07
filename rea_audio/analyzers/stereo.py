# -*- coding: utf-8 -*-
"""Stereo field evidence — inter-channel correlation, mid/side balance."""
import numpy as np

from ..dsp import frame_signal
from ..evidence import Evidence, Finding, FACT


def analyze(x_stereo: np.ndarray, sr: int) -> Finding:
    if x_stereo.ndim != 2 or x_stereo.shape[1] < 2:
        return Finding(id="stereo", title="Stereo field", status="UNKNOWN", confidence=0.0,
                       conclusion="Mono file — no stereo information to analyze")

    ch = x_stereo.shape[1]
    left, right = x_stereo[:, 0], x_stereo[:, min(1, ch - 1)]
    n = min(len(left), len(right))
    left, right = left[:n], right[:n]

    corr = float(np.corrcoef(left, right)[0, 1])
    mid = (left + right) / 2.0
    side = (left - right) / 2.0
    side_ratio = float(np.sqrt(np.mean(side ** 2)) / (np.sqrt(np.mean(mid ** 2)) + 1e-9))

    width = "narrow (near-mono)" if corr > 0.98 else (
        "typical studio pop/rock" if corr > 0.5 else "very wide")
    f = Finding(
        id="stereo", title="Stereo field", status=FACT, confidence=1.0,
        conclusion="L/R correlation {:.3f} — {}; side/mid energy {:.2f}".format(corr, width, side_ratio),
    )
    f.add(Evidence("L/R correlation", round(corr, 4), "r"))
    f.add(Evidence("side/mid RMS ratio", round(side_ratio, 3), "",
                   detail="0 = pure mono, 0.2–0.6 common in mixes, >1 means phase-risky width"))
    if corr > 0.999:
        f.caveats.append("Channels are numerically identical — either a mono upload duplicated to two channels, "
                         "or a synthetic render without stereo decorrelation.")
    return f
