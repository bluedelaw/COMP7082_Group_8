# audio/speech_recognition.py
from __future__ import annotations

import wave
from typing import Optional

import numpy as np
import whisper


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

    # We record mono, 16-bit, 16 kHz in mic.py; assert but still handle common variants.
    if sampwidth != 2:
        raise ValueError(f"Expected 16-bit PCM; got sampwidth={sampwidth}")
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    if nch == 2:
        # simple average to mono if needed
        audio = audio.reshape(-1, 2).mean(axis=1)

    if fr != 16000:
        # We don't expect this in our pipeline; downsample if it happens.
        # Very basic nearest-neighbor resample to avoid bringing in deps.
        ratio = 16000 / float(fr)
        idx = (np.arange(int(len(audio) * ratio)) / ratio).astype(np.int64)
        idx = np.clip(idx, 0, len(audio) - 1)
        audio = audio[idx]

    return audio


def transcribe_audio(file_path: str, model: Optional[whisper.Whisper] = None, device: str = "cpu") -> str:
    """
    Transcribe audio using a provided Whisper model.
    Feeds a numpy waveform directly to avoid ffmpeg invocation.
    """
    local_model = model or whisper.load_model("small", device=device)
    kwargs = {"fp16": device == "cuda"}  # fp16 only on CUDA
    waveform = _wav_to_float32_mono_16k(file_path)
    result = local_model.transcribe(waveform, language="en", **kwargs)
    return result["text"]
