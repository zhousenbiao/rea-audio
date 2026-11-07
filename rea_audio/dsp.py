# -*- coding: utf-8 -*-
"""Shared DSP helpers — frame slicing, STFT, windows. Pure numpy, no heavy deps."""
import numpy as np


def frame_signal(x: np.ndarray, frame_len: int, hop: int) -> np.ndarray:
    """Slice 1-D signal into overlapping frames -> shape (n_frames, frame_len)."""
    if len(x) < frame_len:
        x = np.pad(x, (0, frame_len - len(x)))
    n_frames = 1 + (len(x) - frame_len) // hop
    idx = np.arange(frame_len)[None, :] + hop * np.arange(n_frames)[:, None]
    return x[idx]


def stft_mag(x: np.ndarray, sr: int, frame_ms: float = 40.0, hop_ms: float = 10.0) -> np.ndarray:
    """Magnitude STFT. Returns (n_frames, n_bins) magnitudes (linear)."""
    frame_len = int(sr * frame_ms / 1000.0)
    hop = int(sr * hop_ms / 1000.0)
    frames = frame_signal(x, frame_len, hop)
    win = np.hanning(frame_len)
    spec = np.abs(np.fft.rfft(frames * win[None, :], axis=1))
    return spec


def freqs_of(n_bins: int, sr: int, frame_len: int) -> np.ndarray:
    return np.fft.rfftfreq(frame_len, 1.0 / sr)


def db(x: np.ndarray, floor: float = 1e-10) -> np.ndarray:
    return 20.0 * np.log10(np.maximum(x, floor))


def to_percent(x: float) -> float:
    return round(100.0 * float(x), 1)
