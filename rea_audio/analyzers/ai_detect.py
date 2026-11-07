# -*- coding: utf-8 -*-
"""AI-generation detection — a weighted evidence vote, not an oracle.

Philosophy (inherited from REA): we never say "AI" without showing the numbers
that pushed us there, and every piece of evidence knows what could fake it.
Lossy codecs (low-bitrate MP3), resampling and mastering all imitate parts of
the "AI fingerprint", so each evidence is down-weighted by transport facts.

Evidence lines:
  E1 high-frequency cutoff   — diffusion/vocoder renders often lack energy above ~15–16 kHz
                               (faked by: MP3 <160 kbps, upstream sample rate ≤32 kHz)
  E2 air-band flatness       — synthetic noise floors are unnaturally smooth at 13–18 kHz
  E3 loudness uniformity     — AI renders are consistently loud; human takes breathe more
  E4 onset clocking          — machine-generated grooves have near-zero timing jitter
  E5 stereo anomalies        — numerically identical channels / decorrelated side energy

Verdicts: AI-GENERATED / HUMAN-MADE / INCONCLUSIVE, each with a confidence and
the dominant reasons both ways.
"""
from typing import Dict, List

import numpy as np

from ..dsp import stft_mag
from ..evidence import Evidence, Finding, HYPOTHESIS, UNKNOWN
from .spectrum import measure as measure_spectrum

AI = "AI-GENERATED"
HUMAN = "HUMAN-MADE"
INCONCLUSIVE = "INCONCLUSIVE"


def _onset_jitter(x: np.ndarray, sr: int) -> float:
    """CV (std/mean) of inter-onset intervals — machine clocks barely jitter."""
    spec = stft_mag(x, sr, frame_ms=40.0, hop_ms=10.0)
    flux = np.diff(spec, axis=0)
    flux[flux < 0] = 0.0
    env = flux.sum(axis=1)
    if len(env) < 50:
        return float("nan")
    thr = env.mean() + 1.5 * env.std()
    peaks = []
    for i in range(2, len(env) - 2):
        if env[i] > thr and env[i] == max(env[i - 2:i + 3]):
            if not peaks or i - peaks[-1] >= 10:  # >=100 ms apart
                peaks.append(i)
    ioi = np.diff(peaks)
    ioi = ioi[ioi > 0]
    if len(ioi) < 8:
        return float("nan")
    return float(ioi.std() / (ioi.mean() + 1e-9))


def analyze(x_mono: np.ndarray, sr: int, transport: Dict[str, object]) -> Finding:
    spec_m = measure_spectrum(x_mono, sr)
    rolloff = spec_m["rolloff_hz"]
    rolloff_deep = spec_m.get("rolloff_deep_hz", rolloff)
    air_std = spec_m["air_std_db"]
    nyq = spec_m["nyquist"]
    bitrate = transport.get("bitrate_kbps", 0)
    src_sr = transport.get("sr", sr)

    # how much high-frequency evidence can we trust after the transport?
    hf_trust = 1.0
    if src_sr <= 32000:
        hf_trust = 0.15
    elif bitrate and bitrate < 160:
        hf_trust = 0.25
    elif bitrate and bitrate < 256:
        hf_trust = 0.6

    votes: List[Dict[str, object]] = []
    evs: List[Evidence] = []

    # E1 cutoff & cliff — a human master fades to a noise floor: the -60 dB
    # rolloff lands far beyond the -35 dB one. A neural render stops on a
    # cliff: both rolloffs coincide inside the 8–16.5 kHz band.
    cliff_ratio = (rolloff_deep + 1.0) / (rolloff + 1.0)
    e1_detail = "transport trust ×{:.2f} (bitrate {} kbps, sr {} Hz); cliff ratio {:.2f}".format(
        hf_trust, int(bitrate or 0), src_sr, cliff_ratio)
    if rolloff >= 18500:
        votes.append({"dir": HUMAN, "w": 0.8 * hf_trust,
                      "why": "content extends to {:.1f} kHz".format(rolloff / 1000.0)})
    elif 8000 <= rolloff < 16500 and cliff_ratio < 1.15:
        votes.append({"dir": AI, "w": 1.0 * hf_trust,
                      "why": "hard cliff at {:.1f} kHz (deep rolloff {:.1f} kHz)".format(
                          rolloff / 1000.0, rolloff_deep / 1000.0)})
    elif rolloff < 16500 and cliff_ratio > 1.3:
        votes.append({"dir": HUMAN, "w": 0.5 * hf_trust,
                      "why": "content slopes into a noise floor past {:.1f} kHz (no cliff)".format(
                          rolloff / 1000.0)})
    elif rolloff < 8000:
        e1_detail += "; below 8 kHz — lo-fi/telephone territory, not AI-specific"
    evs.append(Evidence("E1 rolloff", round(rolloff, 0), "Hz", detail=e1_detail))

    # E2 air-band flatness
    if not np.isnan(air_std):
        if air_std < 1.2:
            votes.append({"dir": AI, "w": 0.8 * hf_trust,
                          "why": "13–18 kHz floor suspiciously flat (σ={:.2f} dB)".format(air_std)})
        elif air_std > 2.5:
            votes.append({"dir": HUMAN, "w": 0.5 * hf_trust,
                          "why": "air band wiggles like an analog/noisy floor (σ={:.2f} dB)".format(air_std)})
        evs.append(Evidence("E2 air-band σ", round(air_std, 2), "dB"))

    # E3 loudness uniformity (short-term RMS spread)
    frame_len = int(sr * 0.04)
    spec = stft_mag(x_mono, sr, frame_ms=40.0, hop_ms=20.0)
    rms = np.sqrt((spec ** 2).sum(axis=1))
    top = np.percentile(rms, 95) + 1e-12
    loud_spread = float(rms.std() / top)
    if loud_spread < 0.18:
        votes.append({"dir": AI, "w": 0.5, "why": "loudness almost constant (spread {:.2f})".format(loud_spread)})
    elif loud_spread > 0.35:
        votes.append({"dir": HUMAN, "w": 0.4, "why": "dynamics breathe naturally (spread {:.2f})".format(loud_spread)})
    evs.append(Evidence("E3 loudness spread", round(loud_spread, 3)))

    # E4 onset clocking (CV of inter-onset intervals; live drums sit ~0.03–0.06,
    # quantized machine grooves < 0.01)
    jitter = _onset_jitter(x_mono, sr)
    if not np.isnan(jitter):
        if jitter < 0.012:
            votes.append({"dir": AI, "w": 0.7, "why": "onsets are quantized to a clock (jitter {:.3f})".format(jitter)})
        elif jitter > 0.03:
            votes.append({"dir": HUMAN, "w": 0.5, "why": "human timing drift (jitter {:.3f})".format(jitter)})
        evs.append(Evidence("E4 onset jitter CV", round(jitter, 4)))

    # E5 stereo — a mono file carries no stereo information either way
    st = transport.get("stereo")
    if st and not str(st.get("summary", "")).startswith("Mono file"):
        if st.get("mono_fake"):
            votes.append({"dir": AI, "w": 0.2, "why": "two numerically identical channels"})
        else:
            votes.append({"dir": HUMAN, "w": 0.3, "why": "real stereo image"})
        evs.append(Evidence("E5 stereo", st.get("summary", ""), ""))

    ai_w = sum(v["w"] for v in votes if v["dir"] == AI)
    hu_w = sum(v["w"] for v in votes if v["dir"] == HUMAN)
    total_w = ai_w + hu_w
    if total_w < 0.8:
        verdict, conf = INCONCLUSIVE, 0.0
    elif ai_w > 1.5 * hu_w and ai_w >= 1.2:
        verdict, conf = AI, min(0.85, 0.45 + 0.3 * (ai_w - hu_w))
    elif hu_w > 1.5 * ai_w and hu_w >= 1.2:
        verdict, HUMAN_conf = HUMAN, min(0.8, 0.4 + 0.25 * (hu_w - ai_w))
        conf = HUMAN_conf
    else:
        verdict, conf = INCONCLUSIVE, 0.0

    reasons_ai = [v["why"] for v in votes if v["dir"] == AI]
    reasons_hu = [v["why"] for v in votes if v["dir"] == HUMAN]

    if verdict == INCONCLUSIVE:
        conclusion = ("Evidence is split (AI weight {:.1f} vs human weight {:.1f}) — "
                      "treat as inconclusive".format(ai_w, hu_w))
        status = UNKNOWN
    else:
        conclusion = ("Likely {} (confidence {:.0%}). Pro: {}. Con: {}".format(
            "AI-generated" if verdict == AI else "human-made",
            conf,
            "; ".join(reasons_ai if verdict == AI else reasons_hu)[:200] or "-",
            "; ".join(reasons_hu if verdict == AI else reasons_ai)[:200] or "-"))
        status = HYPOTHESIS

    f = Finding(id="ai_detect", title="AI-generated or human-made?", status=status,
                confidence=conf, conclusion=conclusion)
    f.meta_verdict = verdict  # typed extra for report
    for e in evs:
        f.add(e)
    f.caveats.extend([
        "Heuristic evidence chain — not a trained classifier; a clean master faked through "
        "a lossy pipeline can flip every high-frequency cue.",
        "See eval/RESULTS.md for measured accuracy on the synthetic self-test suite.",
    ])
    return f
