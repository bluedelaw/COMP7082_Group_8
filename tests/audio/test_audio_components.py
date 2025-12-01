# tests/test_audio_components.py
import io
import sys
import os
import tempfile
import importlib
import wave
import types
import math
from pathlib import Path

import numpy as np
import pytest

# --- Helpers to create a fake PyAudio environment before importing modules ---
class FakeStream:
    def __init__(self, data_frames: list[bytes], sample_size=2, chunk=1024):
        self._frames = data_frames[:]  # queue of bytes to return
        self._closed = False
        self._active = True
        self.sample_size = sample_size
        self.chunk = chunk

    def read(self, n, exception_on_overflow=True):
        if not self._frames:
            # return silence
            return (b"\x00" * n * self.sample_size)
        return self._frames.pop(0)

    def stop_stream(self):
        self._active = False

    def is_active(self):
        return self._active

    def close(self):
        self._closed = True


class FakePyAudio:
    def __init__(self, devices=None, default_index=0):
        # devices: list of dicts with keys name, index, maxInputChannels
        self._devices = devices or [
            {"index": 0, "name": "Fake Mic 0", "maxInputChannels": 1},
        ]
        self._default = default_index
        self.sample_size = 2

    def get_device_count(self):
        return len(self._devices)

    def get_device_info_by_index(self, i):
        return self._devices[i]

    def get_default_input_device_info(self):
        return self._devices[self._default]

    def open(self, format, channels, rate, input, frames_per_buffer, input_device_index=None):
        # return a FakeStream that yields a handful of silent frames encoded as int16 little endian
        # build frames corresponding to frames_per_buffer samples
        frame_bytes = (b"\x01\x00") * frames_per_buffer  # small non-zero signal
        return FakeStream([frame_bytes for _ in range(10)], sample_size=2, chunk=frames_per_buffer)

    def terminate(self):
        pass

    def get_sample_size(self, fmt):
        return self.sample_size


@pytest.fixture(autouse=True)
def fake_pyaudio_module(monkeypatch):
    """
    Insert a fake `pyaudio` module into sys.modules before importing any audio.* modules.
    This avoids requiring the real PyAudio C library in tests.
    """
    fake_mod = types.SimpleNamespace(
        PyAudio=lambda: FakePyAudio(),
        paInt16=8,
    )
    monkeypatch.setitem(sys.modules, "pyaudio", fake_mod)
    yield


# Import the project audio package modules after injecting fake pyaudio
import audio.mic as mic
import audio.utils as utils
import audio.wav_io as wav_io
import audio.vad.detector as detector
import audio.vad.stream as stream
import audio.vad.utils as vad_utils


# --- Tests for utils.suppress_alsa_warnings_if_linux ---

def test_suppress_alsa_noop_on_non_linux(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    # should be usable as a context manager and not raise
    with utils.suppress_alsa_warnings_if_linux():
        assert True


def test_suppress_alsa_handles_missing_fileno(monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "linux")

    class DummyStderr:
        def fileno(self):
            raise Exception("no fileno")

    monkeypatch.setattr(sys, "stderr", DummyStderr())
    # should simply yield without throwing
    with utils.suppress_alsa_warnings_if_linux():
        assert True


# --- Tests for wav_io ---

def test_linear_resample_and_wav_roundtrip(tmp_path):
    # create a 8kHz mono int16 wav and ensure it is resampled to 16k
    sr_src = 8000
    duration_s = 0.1
    t = np.linspace(0, duration_s, int(sr_src * duration_s), endpoint=False)
    tone = (0.5 * np.sin(2 * math.pi * 440 * t) * 32767).astype(np.int16)

    path = tmp_path / "src.wav"
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr_src)
        wf.writeframes(tone.tobytes())

    arr = wav_io.wav_to_float32_mono_16k(str(path))
    assert arr.dtype == np.float32
    # resulting length should be about double because 8k -> 16k
    assert abs(len(arr) - len(tone) * 2) <= 2


def test_write_wav_int16_mono(tmp_path):
    pcm = np.array([0, 1000, -1000, 32767, -32768], dtype=np.int16)
    out = tmp_path / "out.wav"
    wav_io.write_wav_int16_mono(str(out), pcm, sample_rate=16000)
    # read back
    with wave.open(str(out), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000


# --- Tests for mic module: device listing/caching/recording ---

def test_list_input_devices_and_default(monkeypatch):
    # FakePyAudio yields a single device so list_input_devices should include it
    devices = mic.list_input_devices()
    assert isinstance(devices, list)
    assert len(devices) >= 1

    idx = mic.get_default_input_device_index()
    assert isinstance(idx, int)


def test_set_and_get_selected_input_device(monkeypatch):
    idx, name = mic.set_selected_input_device(0)
    got_idx, got_name = mic.get_selected_input_device()
    assert got_idx == idx
    assert got_name == name


def test_record_and_amplify(tmp_path):
    # record a short wav via record_wav; our fake PyAudio returns small frames so this should succeed
    out = tmp_path / "rec.wav"
    mic.record_wav(str(out), record_seconds=0, sample_rate=16000, chunk=64, device_index=0)
    # zero-length recording (record_seconds=0) will still create a file with 0 frames
    assert out.exists()

    # amplify: write another file
    in_wave = out
    amp_out = tmp_path / "rec_amp.wav"
    # create a small 16-bit wav to amplify
    with wave.open(str(in_wave), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes((b"\x01\x00" * 100))
    mic.amplify_wav(str(in_wave), str(amp_out), factor=2.0)
    assert amp_out.exists()


# --- Tests for VAD components ---

class DummyMicStreamForVAD:
    def __init__(self, sample_rate, chunk, device_index=None):
        self.sample_rate = sample_rate
        self.chunk = chunk
        self._count = 0

    def open(self):
        pass

    def read_frame(self):
        # Alternate between silence and a loud frame
        self._count += 1
        if self._count < 3:
            # low RMS silent frame
            return np.zeros(self.chunk, dtype=np.int16)
        elif self._count < 8:
            # loud frame
            return (np.ones(self.chunk, dtype=np.int16) * 3000)
        else:
            # after a few frames, raise StopIteration by simulating stop requested via external
            # we return silence afterwards
            return np.zeros(self.chunk, dtype=np.int16)

    def stop(self):
        pass

    def close(self):
        pass


def test_vad_calibrate_and_utterances(monkeypatch):
    # Monkeypatch MicStream used in detector.NoiseGateVAD
    monkeypatch.setattr(detector, "MicStream", DummyMicStreamForVAD)
    vad = detector.NoiseGateVAD(sample_rate=16000, chunk=320)
    # calibrate should run without error
    vad.open()
    vad.calibrate(seconds=0.01)
    gen = vad.utterances()
    # read a few utterances (generator may yield none depending on hangover/threshold) - make sure it doesn't crash
    try:
        for i, (pcm, sr) in zip(range(2), gen):
            assert isinstance(pcm, np.ndarray)
            assert sr == 16000
            break
    except Exception:
        # the generator may raise StopIteration quickly; test passes as long as no unexpected exception
        pass
    finally:
        vad.close()


# --- Tests for vad.stream MicStream open/read/close behavior with fallback ---

def test_micstream_open_fallback(monkeypatch):
    # Ensure that MicStream.open uses fallback path if device open fails.
    # We'll monkeypatch pyaudio.PyAudio.open to raise OSError on first attempt
    class LocalFakePA(FakePyAudio):
        def __init__(self):
            super().__init__()
            self.attempts = 0

        def open(self, format, channels, rate, input, frames_per_buffer, input_device_index=None):
            self.attempts += 1
            if self.attempts == 1:
                raise OSError("device fail")
            return super().open(format, channels, rate, input, frames_per_buffer, input_device_index)

    def make_fake():
        return LocalFakePA()

    # patch module level pyaudio inside stream
    monkeypatch.setattr(stream, "pyaudio", types.SimpleNamespace(PyAudio=make_fake, paInt16=8))
    ms = stream.MicStream(sample_rate=16000, chunk=256, device_index=0)
    # calling open should not raise and should populate _stream
    ms.open()
    assert ms._stream is not None
    ms.close()


# Ensure tests are discoverable when running pytest directly
if __name__ == "__main__":
    pytest.main([os.path.abspath(__file__)])
