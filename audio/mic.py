# audio/mic.py
from __future__ import annotations

import os
import time
import wave
from typing import Optional, Tuple, List

os.environ["PYTHONWARNINGS"] = "ignore"  # optional
os.environ["ALSA_LIB_PATH"] = "/dev/null"
os.environ["ALSA_LOGLEVEL"] = "0"


import numpy as np
import pyaudio
import torch
import whisper

import sys
import contextlib

import config as cfg

# Module-level cache so we don't announce/select the device every chunk
_CACHED_DEVICE_INDEX: Optional[int] = None
_CACHED_DEVICE_NAME: Optional[str] = None

@contextlib.contextmanager
def suppress_alsa_warnings():
    """Suppress ALSA lib warnings to keep logs clean."""
    stderr_fileno = sys.stderr.fileno()
    with open(os.devnull, "w") as devnull:
        old_stderr = os.dup(stderr_fileno)
        os.dup2(devnull.fileno(), stderr_fileno)
        try:
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


def list_input_devices() -> list[tuple[int, str]]:
    """Return list[(index, name)] of input-capable devices."""
    import pyaudio
    devices: list[tuple[int, str]] = []

    with suppress_alsa_warnings():
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
    Automatically pick the first usable input device on Linux (or fallback on any OS).
    Ignores virtual or output-only devices.
    Caches the result to avoid repeated ALSA queries.
    """
    with suppress_alsa_warnings(): 
        p = pyaudio.PyAudio()
        global _CACHED_DEVICE_INDEX, _CACHED_DEVICE_NAME
        if _CACHED_DEVICE_INDEX is not None:
            return _CACHED_DEVICE_INDEX

        import pyaudio

        p = pyaudio.PyAudio()
        devices = []
        try:
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) > 0:
                    # Skip known virtual/output devices
                    name = info.get("name", "").lower()
                    if any(skip in name for skip in ("hdmi", "pulse", "jack", "dmix", "output")):
                        continue
                    devices.append((i, info["name"], int(info.get("defaultSampleRate", 48000))))
        finally:
            p.terminate()

        if not devices:
            raise RuntimeError("No usable input devices found. Check mic permissions.")

        idx, name, rate = devices[0]
        _CACHED_DEVICE_INDEX = idx
        _CACHED_DEVICE_NAME = name
        print(f"🎤 Using input device [{idx}] {name} | default rate={rate} Hz")
    return idx



def record_wav(filename="output.wav", record_seconds=5, device_index=None, rate=48000):
    """
    Records audio to a WAV file, suppressing ALSA warnings.
    
    Args:
        filename (str): Name of output WAV file.
        record_seconds (int): Recording duration in seconds.
        device_index (int or None): PyAudio input device index.
        rate (int): Sampling rate (Hz).
    """
    p = pyaudio.PyAudio()
    frames = []
    chunk_size = 1024
    channels = 1  # usually 1 for microphone

    with suppress_alsa_warnings():
        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                frames_per_buffer=chunk_size,
                input_device_index=device_index
            )
        except Exception as e:
            print(f"Failed to open audio device: {e}")
            p.terminate()
            return

        print(f"Recording for {record_seconds} seconds…")
        for _ in range(0, int(rate / chunk_size * record_seconds)):
            data = stream.read(chunk_size, exception_on_overflow=False)
            frames.append(data)

        stream.stop_stream()
        stream.close()
        p.terminate()

    # Save to WAV
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))

    print(f"Recording saved as {filename}")

    
    


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
