# -*- coding: utf-8 -*-
"""Audio loading — one place that turns any file into (mono float array, sr, channels)."""
from typing import Tuple, Optional

import numpy as np
import soundfile as sf


def load_audio(path: str, mono: bool = True) -> Tuple[np.ndarray, int, int]:
    """Load any libsndfile-supported file (wav/flac/ogg/mp3...).

    Returns (samples, sample_rate, original_channels).
    samples is float32 in [-1, 1]; if mono=True multi-channel is averaged.
    """
    data, sr = sf.read(path, always_2d=True, dtype="float32")
    channels = data.shape[1]
    if mono:
        mono_data = data.mean(axis=1)
    else:
        mono_data = data
    return np.ascontiguousarray(mono_data), int(sr), channels


def load_info(path: str) -> dict:
    info = sf.info(path)
    return {
        "sr": info.samplerate,
        "channels": info.channels,
        "frames": info.frames,
        "duration": info.duration,
        "format": info.format,
        "subtype": info.subtype,
        "codec": getattr(info, "codec", None) or "",
        "bits_per_sample": getattr(info, "bits_per_sample", None),
    }


def resample(x: np.ndarray, sr_from: int, sr_to: int) -> np.ndarray:
    """Cheap sinc-free linear resampler — fine for analysis features, not for listening."""
    if sr_from == sr_to:
        return x
    n_out = int(round(len(x) * sr_to / sr_from))
    idx = np.linspace(0.0, len(x) - 1.0, n_out)
    idx0 = np.floor(idx).astype(np.int64)
    idx1 = np.minimum(idx0 + 1, len(x) - 1)
    frac = idx - idx0
    return (x[idx0] * (1 - frac) + x[idx1] * frac).astype(x.dtype)
