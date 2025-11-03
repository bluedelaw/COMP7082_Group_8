# audio/wav_io.py
from __future__ import annotations

import wave
import numpy as np
from audio.utils import write_wav_int16_mono as _write_wav_int16_mono


def linear_resample(audio: np.ndarray, src_hz: int, dst_hz: int) -> np.ndarray:
    if src_hz == dst_hz or audio.size == 0:
        return audio.astype(np.float32, copy=False)
    ratio = float(dst_hz) / float(src_hz)
    n = int(round(len(audio) * ratio))
    xp = np.linspace(0.0, 1.0, num=len(audio), endpoint=False, dtype=np.float64)
    fp = audio.astype(np.float64, copy=False)
    x_new = np.linspace(0.0, 1.0, num=n, endpoint=False, dtype=np.float64)
    y = np.interp(x_new, xp, fp).astype(np.float32, copy=False)
    return y


def wav_to_float32_mono_16k(path: str) -> np.ndarray:
    with wave.open(path, "rb") as wf:
        nch = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        fr = wf.getframerate()
        nframes = wf.getnframes()
        audio_bytes = wf.readframes(nframes)

    if sampwidth != 2:
        raise ValueError(f"Expected 16-bit PCM; got sampwidth={sampwidth}")

    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    if nch == 2:
        audio = audio.reshape(-1, 2).mean(axis=1).astype(np.float32, copy=False)

    if fr != 16000:
        audio = linear_resample(audio, src_hz=fr, dst_hz=16000)

    return audio


def write_wav_int16_mono(path: str, pcm: np.ndarray, sample_rate: int, normalize_dbfs: float | None = None) -> None:
    _write_wav_int16_mono(path, pcm, sample_rate, normalize_dbfs)
