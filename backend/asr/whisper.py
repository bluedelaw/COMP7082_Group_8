# backend/asr/whisper.py
from __future__ import annotations
from typing import Optional
from audio.speech_recognition import transcribe_audio, get_cached_model_and_device

class WhisperASR:
    """
    Thin adapter implementing ASRTranscriber over the existing Whisper functions.
    Construct once and reuse (reuses the cached whisper model/device under the hood).
    """
    def __init__(self, model_size: Optional[str] = None) -> None:
        # Use the global cached model/device to avoid repeated loads
        self.model, self.device = get_cached_model_and_device(model_size)

    def transcribe(self, wav_path: str) -> str:
        return transcribe_audio(wav_path, model=self.model, device=self.device)
