# audio/mic.py
from __future__ import annotations

import os
import sys
import time
import wave
import contextlib
from typing import Optional, Tuple, List

import numpy as np
import pyaudio
import torch
import whisper

import config as cfg

# Module-level cache so we don't re-select the device every call
_CACHED_DEVICE_INDEX: Optional[int] = None
_CACHED_DEVICE_NAME: Optional[str] = None


# --- Linux-only: suppress noisy ALSA lib warnings during device enumeration ---
@contextlib.contextmanager
def _suppress_alsa_warnings_if_linux():
    if not sys.platform.startswith("linux"):
        # No-op on non-Linux
        yield
        return
    stderr_fileno = sys.stderr.fileno()
    with open(os.devnull, "w") as devnull:
        old_stderr = os.dup(stderr_fileno)
        try:
            os.dup2(devnull.fileno(), stderr_fileno)
            yield
        finally:
            os.dup2(old_stderr, stderr_fileno)
            os.close(old_stderr)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def ensure_temp() -> None:
    ensure_dir(cfg.TEMP_DIR)


def detect_model_size() -> str:
    """
    Heuristic to choose a Whisper model size based on GPU VRAM.
    Falls back to 'base' on CPU.
    """
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        vram_gb = props.total_memory / (1024 ** 3)
        if vram_gb < 4:
            return "tiny"
        elif vram_gb < 6:
            return "base"
        elif vram_gb < 10:
            return "small"
        elif vram_gb < 16:
            return "medium"
        else:
            return "large"
    return "base"


def load_whisper_model(model_size: Optional[str] = None) -> Tuple[whisper.Whisper, str, str]:
    """
    Load a Whisper model once. Returns (model, device, model_size).
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    size = model_size if model_size is not None else (cfg.WHISPER_MODEL_SIZE or detect_model_size())

    print(f"🧠 Loading Whisper model '{size}' on {device}...")
    model = whisper.load_model(size, device=device)
    if device == "cuda":
        model.half()
    return model, device, size


def list_input_devices() -> List[Tuple[int, str]]:
    """
    Return list[(index, name)] of input-capable devices.
    """
    devices: List[Tuple[int, str]] = []
    with _suppress_alsa_warnings_if_linux():
        p = pyaudio.PyAudio()
        try:
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) > 0:
                    devices.append((i, info["name"]))
        finally:
            p.terminate()
    return devices


def get_default_input_device_index() -> int:
    """
    Prefer PyAudio's default input device. Fallback to first input-capable device.
    Result is cached for the process lifetime.
    """
    global _CACHED_DEVICE_INDEX, _CACHED_DEVICE_NAME
    if _CACHED_DEVICE_INDEX is not None:
        return _CACHED_DEVICE_INDEX

    with _suppress_alsa_warnings_if_linux():
        p = pyaudio.PyAudio()
        try:
            try:
                info = p.get_default_input_device_info()
                idx = int(info.get("index"))
                name = str(info.get("name"))
            except Exception:
                # Fallback: first input-capable device
                devices = list_input_devices()
                if not devices:
                    raise RuntimeError("No input devices found. Check microphone permissions.")
                idx, name = devices[0]
        finally:
            p.terminate()

    _CACHED_DEVICE_INDEX = idx
    _CACHED_DEVICE_NAME = name
    print(f"🎤 Using input device [{idx}] {name}")
    return idx


def record_wav(
    filename: str,
    record_seconds: int = cfg.RECORD_SECONDS,
    sample_rate: int = cfg.SAMPLE_RATE,
    chunk: int = cfg.CHUNK,
    device_index: Optional[int] = None,
) -> None:
    """
    Record mono 16-bit PCM WAV at the configured sample rate.
    Robust against occasional buffer overruns.
    """
    ensure_dir(os.path.dirname(filename) or ".")
    p = pyaudio.PyAudio()

    if device_index is None:
        device_index = get_default_input_device_index()

    # Try to open the chosen device; on failure, fall back to default stream
    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=chunk,
            input_device_index=device_index,
        )
    except OSError:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=chunk,
        )

    frames: List[bytes] = []
    try:
        for _ in range(0, int(sample_rate / chunk * record_seconds)):
            # Tolerate occasional overflow on busy systems
            data = stream.read(chunk, exception_on_overflow=False)
            frames.append(data)
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(frames))


def amplify_wav(input_filename: str, output_filename: str, factor: float = cfg.AMP_FACTOR) -> str:
    """
    Simple int16 amplification with clipping.
    """
    with wave.open(input_filename, "rb") as wf:
        params = wf.getparams()
        frames = wf.readframes(wf.getnframes())
        audio = np.frombuffer(frames, dtype=np.int16)

    amplified = np.clip(audio * factor, -32768, 32767).astype(np.int16)

    ensure_dir(os.path.dirname(output_filename) or ".")
    with wave.open(output_filename, "wb") as wf:
        wf.setparams(params)
        wf.writeframes(amplified.tobytes())
    return output_filename


def _ts() -> str:
    # Timestamp good for filenames (local time). Example: 20250922_153045_123
    t = time.localtime()
    return time.strftime("%Y%m%d_%H%M%S", t) + f"_{int((time.time()%1)*1000):03d}"


def record_and_prepare_chunk(
    basename: str = "chunk",
    seconds: int = cfg.RECORD_SECONDS,
    amp_factor: float = cfg.AMP_FACTOR,
    device_index: Optional[int] = None,
    out_dir: Optional[str] = None,
    persist: bool = False,
) -> str:
    """
    Records a chunk and returns the path to the amplified WAV.

    - If persist=True, files are written under 'out_dir' with timestamped names.
    - If persist=False, files live under TEMP_DIR and are overwritten every cycle:
        - raw:  <TEMP_DIR>/live_raw.wav
        - amp:  <TEMP_DIR>/live_amp.wav
      Optionally deletes the raw file after amplifying (cfg.DELETE_RAW_AFTER_AMPLIFY).
    """
    if persist:
        assert out_dir, "out_dir must be provided when persist=True"
        ensure_dir(out_dir)
        stamp = _ts()
        raw = os.path.join(out_dir, f"{basename}_{stamp}_raw.wav")
        amp = os.path.join(out_dir, f"{basename}_{stamp}_amp.wav")
        record_wav(raw, record_seconds=seconds, device_index=device_index)
        amplify_wav(raw, amp, factor=amp_factor)
        return amp
    else:
        ensure_temp()
        raw = os.path.join(cfg.TEMP_DIR, "live_raw.wav")
        amp = os.path.join(cfg.TEMP_DIR, "live_amp.wav")
        record_wav(raw, record_seconds=seconds, device_index=device_index)
        amplify_wav(raw, amp, factor=amp_factor)
        if cfg.DELETE_RAW_AFTER_AMPLIFY:
            try:
                os.remove(raw)
            except OSError:
                pass
        return amp
