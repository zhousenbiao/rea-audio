# -*- coding: utf-8 -*-
"""AI-generation detection — a weighted evidence vote, not an oracle.

Philosophy (inherited from REA): we never say "AI" without showing the numbers
that pushed us there, and every piece of evidence knows what could fake it.
Lossy codecs (low-bitrate MP3), resampling and mastering all imitate parts of
the "AI fingerprint", so each evidence is down-weighted by transport facts.

Calibrated on real tracks (see cases/): Suno v5-era renders and human masters
are separated by the *generation-band edge* — modern neural renderers carry
content to ~17 kHz and then drop steeply, human masters stay comparatively flat
through the air band.

Evidence lines:
  E1 generation-band edge  — LTAS(16–19 kHz) vs LTAS(13–15 kHz): a steep drop
                             is the neural-renderer fingerprint; also handles
                             low-bandwidth renders and transport cliffs
                             (faked by: MP3 <128 kbps, upstream sr ≤32 kHz)
  E2 air-band texture      — only meaningful once E1 says the air band exists
  E3 loudness uniformity   — AI renders are consistently loud; human takes breathe more
  E4 onset clocking        — machine-generated grooves have near-zero timing jitter
  E5 stereo anomalies      — numerically identical channels / real stereo image

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
    air_slope = spec_m.get("air_slope_db", float("nan"))
    air_decay = spec_m.get("air_decay_db", float("nan"))
    air_floor = spec_m.get("air_floor_db", float("nan"))
    air_std = spec_m["air_std_db"]
    nyq = spec_m["nyquist"]
    bitrate = transport.get("bitrate_kbps", 0)
    src_sr = transport.get("sr", sr)
    codec = str(transport.get("codec", "") or "")

    # how much high-frequency evidence can we trust after the transport?
    # Judge by the measured bandwidth, not just the codec label: if the deep
    # rolloff demonstrably reaches ≥17 kHz, the air band survived transport and
    # the edge evidence is trustworthy regardless of bitrate. Lossless codecs
    # never low-pass, so they start at full trust.
    lossless = codec.startswith(("WAV", "FLAC", "AIFF", "PCM"))
    if src_sr <= 32000:
        hf_trust = 0.15
    elif lossless:
        hf_trust = 1.0
    elif rolloff_deep >= 17000.0:
        hf_trust = 1.0
    elif bitrate and bitrate < 128:
        hf_trust = 0.25
    elif bitrate and bitrate < 192:
        hf_trust = 0.45
    elif bitrate and bitrate < 256:
        hf_trust = 0.75
    else:
        hf_trust = 0.9

    votes: List[Dict[str, object]] = []
    evs: List[Evidence] = []

    # E1 generation-band edge — the calibrated separator between Suno v5-era
    # renders (steep drop past 16 kHz) and human masters (flat air band).
    # Fallbacks: low-bandwidth renders, and legacy hard cliffs.
    air_share = float(spec_m.get("band_shares", {}).get("air", 0.0))
    air_share_med = float(spec_m.get("band_shares", {}).get("air_med", 0.0))
    e1_detail = ("transport trust ×{:.2f} (bitrate {} kbps, sr {} Hz)".format(
        hf_trust, int(bitrate or 0), src_sr) if not np.isnan(air_slope) else "air band not measurable")
    if src_sr <= 32000 or np.isnan(air_slope):
        e1_detail = "source sample rate {} Hz — air band not measurable, E1 abstains".format(src_sr)
    elif air_slope <= -15.0:
        votes.append({"dir": AI, "w": 1.0 * hf_trust,
                      "why": "generation-band edge: air band drops {:.1f} dB over 13→16 kHz "
                             "(decay vs 8–12 kHz: {:.1f} dB)".format(air_slope, air_decay)})
    elif air_slope <= -10.0 and air_decay <= -30.0:
        votes.append({"dir": AI, "w": 0.7 * hf_trust,
                      "why": "steep air-band drop-off (edge {:.1f} dB, decay {:.1f} dB)".format(
                          air_slope, air_decay)})
    elif rolloff_deep < 13000.0 and abs(air_slope) < 3.0 and air_share_med < 0.0002:
        # nothing above 13 kHz at all and pre-air/air sit on the same numeric
        # floor — a band-limited render (or a lo-fi source; see caveat)
        votes.append({"dir": AI, "w": 0.8 * hf_trust,
                      "why": "band-limited render: no persistent content above 12 kHz "
                             "(deep rolloff {:.1f} kHz)".format(rolloff_deep / 1000.0)})
    elif air_slope > -8.0 and air_decay > -18.0 and air_share_med > 0.0004:
        votes.append({"dir": HUMAN, "w": 0.7 * hf_trust,
                      "why": "air band carries persistent content through 19 kHz "
                             "(edge {:.1f} dB, persistent share {:.4f})".format(air_slope, air_share_med)})
    evs.append(Evidence("E1 air-band edge", round(air_slope, 1) if not np.isnan(air_slope) else "n/a",
                        "dB", detail=e1_detail))

    # E2 air-band texture — only votes once the air band demonstrably exists;
    # a steep edge (E1 territory) makes σ large for mechanical reasons
    if not np.isnan(air_std) and not np.isnan(air_slope) and air_slope > -15.0:
        if air_std > 2.5:
            votes.append({"dir": HUMAN, "w": 0.3 * hf_trust,
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

    # E4 onset clocking (CV of inter-onset intervals; only the machine-clock
    # side has proven discriminative on real music — live grooves, syncopation
    # and swing inflate CV well past any human threshold, so no human vote here)
    jitter = _onset_jitter(x_mono, sr)
    if not np.isnan(jitter):
        if jitter < 0.012:
            votes.append({"dir": AI, "w": 0.7, "why": "onsets are quantized to a clock (jitter {:.3f})".format(jitter)})
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
    # verdict thresholds: one strong calibrated evidence (w≈1.0) may decide on
    # its own if the other side has less than half its weight; otherwise demand
    # converging evidence
    if ai_w >= 0.95 and ai_w >= 2.0 * hu_w:
        verdict, conf = AI, min(0.85, 0.45 + 0.3 * (ai_w - hu_w))
    elif hu_w >= 0.95 and hu_w >= 2.0 * ai_w:
        verdict, conf = HUMAN, min(0.8, 0.4 + 0.25 * (hu_w - ai_w))
    elif ai_w >= 1.5 and ai_w > 1.5 * hu_w:
        verdict, conf = AI, min(0.85, 0.55 + 0.2 * (ai_w - hu_w))
    elif hu_w >= 1.5 and hu_w > 1.5 * ai_w:
        verdict, conf = HUMAN, min(0.8, 0.5 + 0.18 * (hu_w - ai_w))
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
