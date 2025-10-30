# audio/speech_recognition.py
from __future__ import annotations

from typing import Optional, Tuple
from functools import lru_cache

import numpy as np
import whisper
import torch

from audio.wav_io import wav_to_float32_mono_16k


def _best_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    try:
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
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


def get_cached_model_and_device(model_size: Optional[str] = None) -> Tuple[whisper.Whisper, str]:
    """
    Public accessor for the cached Whisper model + device.
    Keeps a single source of truth for ASR lifecycle across the app.
    """
    return _get_model_and_device(model_size)


def transcribe_audio(
    file_path: str,
    model: Optional[whisper.Whisper] = None,
    device: str = "cpu",
) -> str:
    """
    Transcribe audio from a file path. If a model/device is provided, use it;
    otherwise use the cached singleton model+device.
    """
    if model is None:
        model, device = _get_model_and_device(None)

    waveform: np.ndarray = wav_to_float32_mono_16k(file_path)
    kwargs = {"fp16": device == "cuda"}
    result = model.transcribe(waveform, language="en", **kwargs)
    return result["text"]
