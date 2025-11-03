# audio/mic.py
from __future__ import annotations

import os
import time
import wave
import logging
from typing import Optional, List, Tuple

import numpy as np
import pyaudio

import config as cfg
from audio.utils import suppress_alsa_warnings_if_linux

log = logging.getLogger("jarvin.mic")

_CACHED_DEVICE_INDEX: Optional[int] = None
_CACHED_DEVICE_NAME: Optional[str] = None


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def ensure_temp() -> None:
    os.makedirs(cfg.settings.temp_dir, exist_ok=True)


def list_input_devices() -> List[Tuple[int, str]]:  # type: ignore[name-defined]
    devices: List[Tuple[int, str]] = []
    with suppress_alsa_warnings_if_linux():
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
    global _CACHED_DEVICE_INDEX, _CACHED_DEVICE_NAME
    if _CACHED_DEVICE_INDEX is not None:
        return _CACHED_DEVICE_INDEX

    with suppress_alsa_warnings_if_linux():
        p = pyaudio.PyAudio()
        try:
            try:
                info = p.get_default_input_device_info()
                idx = int(info.get("index"))
                name = str(info.get("name"))
            except Exception:
                devices = list_input_devices()
                if not devices:
                    raise RuntimeError("No input devices found. Check microphone permissions.")
                idx, name = devices[0]
        finally:
            p.terminate()

    _CACHED_DEVICE_INDEX = idx
    _CACHED_DEVICE_NAME = name
    log.info("🎤 Using input device [%d] %s", idx, name)
    return idx


def record_wav(
    filename: str,
    record_seconds: int = None,
    sample_rate: int = None,
    chunk: int = None,
    device_index: Optional[int] = None,
) -> None:
    """
    Record mono 16-bit PCM WAV at the configured sample rate.
    """
    s = cfg.settings
    record_seconds = s.record_seconds if record_seconds is None else record_seconds
    sample_rate = s.sample_rate if sample_rate is None else sample_rate
    chunk = s.chunk if chunk is None else chunk

    ensure_dir(os.path.dirname(filename) or ".")
    p = pyaudio.PyAudio()

    if device_index is None:
        device_index = get_default_input_device_index()

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


def amplify_wav(input_filename: str, output_filename: str, factor: float = None) -> str:
    s = cfg.settings
    factor = s.amp_factor if factor is None else factor
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
    t = time.localtime()
    return time.strftime("%Y%m%d_%H%M%S", t) + f"_{int((time.time()%1)*1000):03d}"


def record_and_prepare_chunk(
    basename: str = "chunk",
    seconds: int = None,
    amp_factor: float = None,
    device_index: Optional[int] = None,
    out_dir: Optional[str] = None,
    persist: bool = False,
) -> str:
    """
    Records a chunk and returns the path to the amplified WAV.
    """
    s = cfg.settings
    seconds = s.record_seconds if seconds is None else seconds
    amp_factor = s.amp_factor if amp_factor is None else amp_factor

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
        raw = os.path.join(s.temp_dir, "live_raw.wav")
        amp = os.path.join(s.temp_dir, "live_amp.wav")
        record_wav(raw, record_seconds=seconds, device_index=device_index)
        amplify_wav(raw, amp, factor=amp_factor)
        if s.delete_raw_after_amplify:
            try:
                os.remove(raw)
            except OSError:
                pass
        return amp
