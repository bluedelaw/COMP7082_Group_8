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
try:
    import pyaudio
except ImportError:
    pyaudio = None

import torch
import whisper
import threading
from contextlib import contextmanager, suppress

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

def print_input_devices():
    devices = list_input_devices()
    if not devices:
        print("❌ No input devices found.", flush=True)
    else:
        print("🎤 Input-capable devices:", flush=True)
        for idx, name in devices:
            print(f"  [{idx}] {name}", flush=True)


def get_default_input_device_index():
    global pyaudio
    print("🔍 Checking PyAudio import:", pyaudio)
    if pyaudio is None:
        print("❌ PyAudio not available. Please install it with: pip install pyaudio")
        raise RuntimeError("PyAudio not available")

    p = pyaudio.PyAudio()
    count = p.get_device_count()
    print(f"🎤 Found {count} audio devices")

    if count == 0:
        raise RuntimeError("❌ No input audio devices found.")

    info = p.get_default_input_device_info()
    print("✅ Default input device:", info)
    return info.get("index")




def record_wav(filename="output.wav", record_seconds=5, device_index=None):
    import pyaudio, wave, time

    frames = []
    rate = 44100
    frames_per_buffer = 1024

    p = pyaudio.PyAudio()
    if device_index is None:
        device_index = p.get_default_input_device_info()['index']

    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=rate,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=frames_per_buffer)
    
    print(f"🎙️ Recording for {record_seconds}s…", flush=True)
    start_time = time.time()
    
    while time.time() - start_time < record_seconds:
        try:
            data = stream.read(frames_per_buffer, exception_on_overflow=False)
            frames.append(data)
        except Exception as e:
            print(f"❌ Error capturing audio: {e}", flush=True)
    
    stream.stop_stream()
    stream.close()
    p.terminate()

    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))

    print(f"✅ Recording saved as {filename}", flush=True)

  
    


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


# Now you can safely call it
if __name__ == "__main__":
    print_input_devices()