# -*- coding: utf-8 -*-
"""Long-term average spectrum (LTAS) evidence — rolloff, band energy, high-frequency shape.

These are the raw measurements the AI-detection analyzer reasons over. They are
deliberately kept separate from any verdict: numbers first, interpretation later.
"""
from typing import Dict, List

import numpy as np

from ..dsp import stft_mag, freqs_of, db

BANDS = [
    ("sub",       20,     60),
    ("bass",      60,    250),
    ("low-mid",  250,    500),
    ("mid",      500,   2000),
    ("high-mid",2000,   4000),
    ("presence", 4000,  6000),
    ("brilliance",6000, 12000),
    ("air",     12000, 20000),
]


def measure(x: np.ndarray, sr: int) -> Dict[str, object]:
    frame_len = int(sr * 0.04)
    spec = stft_mag(x, sr, frame_ms=40.0, hop_ms=20.0)
    freqs = freqs_of(spec.shape[1], sr, frame_len)
    ltas = db(spec.mean(axis=0))                 # dB per bin, long-term average
    peak_db = ltas.max()

    def avg_db(lo: float, hi: float) -> float:
        band = (freqs >= lo) & (freqs < min(hi, sr / 2.0))
        if not band.any():
            return -120.0
        return float(ltas[band].mean())

    band_db = {name: avg_db(lo, hi) for name, lo, hi in BANDS}

    # spectral rolloffs at two depths: the gap between them separates a
    # gentle slope-with-no-floor (human recordings) from a hard cliff
    # (older neural renders that simply stop).
    def rolloff_at(depth_db: float) -> float:
        # last bin still above threshold — LTAS is non-monotonic (a piano dips
        # mid-band then rises into the air/noise floor), so "first bin below"
        # would report the dip, not where content actually ends
        above = ltas > (peak_db - depth_db)
        idx = np.where(above)[0]
        return float(freqs[idx[-1]]) if len(idx) else 0.0

    rolloff = rolloff_at(35.0)   # shallow: where content fades below -35 dB
    rolloff_deep = rolloff_at(60.0)  # deep:   where even the noise floor dies

    def band_mean(lo: float, hi: float) -> float:
        b = (freqs >= lo) & (freqs < min(hi, sr / 2.0 - 500.0))
        return float(ltas[b].mean()) if b.any() else float("nan")

    # generation-band edge: modern neural renderers (Suno v5-era) carry content
    # up to ~17 kHz but drop steeply after; human masters stay flat through the
    # air band. air_slope = LTAS(16–19k) − LTAS(13–15k); air_decay is the same
    # measured against 8–12 kHz.
    air_slope = band_mean(16000, 19000) - band_mean(13000, 15000)
    air_decay = band_mean(16000, 19000) - band_mean(8000, 12000)
    air_floor = band_mean(13000, 15000) - peak_db   # how alive the pre-air band is

    # air-band flatness: std of LTAS 13k..18k — analog noise floors wiggle, synthetic ones often don't
    air_band = (freqs >= 13000) & (freqs <= min(18000, sr / 2.0 - 500))
    air_std = float(ltas[air_band].std()) if air_band.sum() > 10 else float("nan")

    # energy shares (linear power)
    power = spec.mean(axis=0)
    total = power.sum() + 1e-12
    shares = {}
    for name, lo, hi in BANDS:
        band = (freqs >= lo) & (freqs < min(hi, sr / 2.0))
        shares[name] = float(power[band].sum() / total)

    # persistent air share: median over frames instead of mean — broadband
    # transients (clicks, hats) splash energy into the air band for a few
    # frames, but only a real noise floor / room tone / cymbal tail keeps it
    # there in *most* frames
    air_band_idx = (freqs >= 12000) & (freqs < min(20000, sr / 2.0))
    if air_band_idx.any() and spec.shape[0] > 0:
        air_frame = spec[:, air_band_idx].sum(axis=1)
        tot_frame = spec.sum(axis=1) + 1e-12
        shares["air_med"] = float(np.median(air_frame) / np.median(tot_frame))
    else:
        shares["air_med"] = 0.0

    return {
        "sr": sr, "nyquist": sr / 2.0,
        "ltas": ltas, "freqs": freqs,
        "peak_db": float(peak_db),
        "rolloff_hz": rolloff,
        "rolloff_deep_hz": rolloff_deep,
        "air_slope_db": float(air_slope),
        "air_decay_db": float(air_decay),
        "air_floor_db": float(air_floor),
        "air_std_db": air_std,
        "band_db": band_db,
        "band_shares": shares,
    }


def analyze(x: np.ndarray, sr: int) -> "Finding":
    from ..evidence import Evidence, Finding, FACT
    m = measure(x, sr)
    band_db = m["band_db"]
    f = Finding(
        id="spectrum", title="Spectral balance", status=FACT, confidence=1.0,
        conclusion="Rolloff(-35 dB) {:.1f} kHz; dominant band: {}".format(
            m["rolloff_hz"] / 1000.0,
            max(band_db, key=lambda k: band_db[k])),
    )
    f.add(Evidence("rolloff frequency", round(m["rolloff_hz"], 0), "Hz"))
    f.add(Evidence("air-band LTAS std", round(m["air_std_db"], 2), "dB",
                   detail="13–18 kHz roughness; analog noise floors wiggle more than synthetic ones"))
    ev = Evidence("band energies", {k: round(v, 1) for k, v in band_db.items()}, "dB")
    ev.labels = ["{}: {} dB".format(k, round(v, 1)) for k, v in band_db.items()]
    f.add(ev)
    # decimated LTAS snapshot for the report chart (60 points, log-spaced)
    freqs, ltas = m["freqs"], m["ltas"]
    keep = freqs > 30
    freqs, ltas = freqs[keep], ltas[keep]
    step = max(1, len(freqs) // 60)
    snap = Evidence("LTAS snapshot", "", "",
                    detail="long-term average spectrum, log-spaced decimation",
                    snapshot=[float(v) for v in ltas[::step]],
                    labels=["{:.1f}k".format(v / 1000.0) for v in freqs[::step]])
    f.add(snap)
    return f, m
