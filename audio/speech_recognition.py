# audio/speech_recognition.py
from __future__ import annotations

import wave
from typing import Optional
from functools import lru_cache

import numpy as np
import whisper
import torch


def _wav_to_float32_mono_16k(path: str) -> np.ndarray:
    """
    Load a WAV recorded by our pipeline (mono, 16-bit) into float32 [-1, 1] at 16 kHz.
    Avoids ffmpeg so shutdowns are clean.
    """
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
        audio = audio.reshape(-1, 2).mean(axis=1)

    if fr != 16000:
        # simple linear resample to 16k without extra deps
        ratio = 16000 / float(fr)
        n = int(round(len(audio) * ratio))
        xp = np.linspace(0.0, 1.0, num=len(audio), endpoint=False, dtype=np.float64)
        fp = audio.astype(np.float64)
        x_new = np.linspace(0.0, 1.0, num=n, endpoint=False, dtype=np.float64)
        audio = np.interp(x_new, xp, fp).astype(np.float32)

    return audio


def _best_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    try:
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():  # Apple Silicon
            return "mps"
    except Exception:
        pass
    return "cpu"


@lru_cache(maxsize=1)
def _get_model_and_device(model_size: Optional[str] = None) -> tuple[whisper.Whisper, str]:
    """
    Process-wide cached Whisper model.
    """
    device = _best_device()
    size = model_size or "small"
    model = whisper.load_model(size, device=device)
    if device == "cuda":
        model.half()
    return model, device


def transcribe_audio(
    file_path: str,
    model: Optional[whisper.Whisper] = None,
    device: str = "cpu",
) -> str:
    """
    Transcribe audio. If a model/device is provided, use it; otherwise use the cached singleton.
    """
    if model is None:
        model, device = _get_model_and_device(None)

    waveform = _wav_to_float32_mono_16k(file_path)
    kwargs = {"fp16": device == "cuda"}
    result = model.transcribe(waveform, language="en", **kwargs)
    return result["text"]
