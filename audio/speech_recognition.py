# speech_recognition.py
from __future__ import annotations

from typing import Optional
import whisper


def transcribe_audio(file_path: str, model: Optional[whisper.Whisper] = None, device: str = "cpu") -> str:
    """
    Transcribe a WAV/MP3 using a provided Whisper model.
    If no model is provided, load a small default (slower).
    """
    local_model = model or whisper.load_model("small", device=device)
    kwargs = {"fp16": device == "cuda"}  # fp16 only on CUDA
    result = local_model.transcribe(file_path, language="en", **kwargs)
    return result["text"]
