# audio/vad.py
from __future__ import annotations

import collections
import logging
import os
import sys
import time
import wave
from typing import Callable, Deque, Generator, Optional, Tuple

import numpy as np
import pyaudio

import config as cfg
from audio.mic import _suppress_alsa_warnings_if_linux, get_default_input_device_index

Int16 = np.int16
log = logging.getLogger("jarvin.vad")

def _rms_int16(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    y = x.astype(np.float32)
    return float(np.sqrt(np.mean(y * y)))

def _isatty(stream) -> bool:
    try:
        return stream.isatty()
    except Exception:
        return False

class _TTYStatus:
    def __init__(self) -> None:
        s = cfg.settings
        self.enabled = s.vad_tty_status and _isatty(sys.stderr)
        self._last_str = ""

    def update(self, s: str) -> None:
        if not self.enabled or s == self._last_str:
            return
        sys.stderr.write("\r" + s + "\x1b[K")
        sys.stderr.flush()
        self._last_str = s

    def clear(self) -> None:
        if not self.enabled:
            return
        sys.stderr.write("\r\x1b[K")
        sys.stderr.flush()
        self._last_str = ""

class NoiseGateVAD:
    def __init__(
        self,
        sample_rate: int = None,
        chunk: int = None,
        device_index: Optional[int] = None,
        on_recording: Optional[Callable[[bool], None]] = None,
    ) -> None:
        s = cfg.settings
        self.sample_rate = s.sample_rate if sample_rate is None else sample_rate
        self.chunk = s.chunk if chunk is None else chunk
        self.device_index = device_index
        self._pa: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None

        self._last_heartbeat_ts = 0.0
        self._last_thr_log_ts = 0.0
        self._frame_idx = 0
        self._stop_requested = False
        self._status = _TTYStatus()

        self.frame_ms = int((self.chunk / self.sample_rate) * 1000)
        self.alpha_floor = 0.98
        self.alpha_env = 0.85

        self.floor_rms = 50.0
        self.env_rms = 0.0

        self._on_recording = on_recording

    def __enter__(self) -> "NoiseGateVAD":
        self.open()
        self._notify_recording(False)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            self.close()
        finally:
            self._notify_recording(False)
        return False

    def open(self) -> None:
        if self._pa:
            return
        self._pa = pyaudio.PyAudio()
        if self.device_index is None:
            self.device_index = get_default_input_device_index()
        with _suppress_alsa_warnings_if_linux():
            try:
                self._stream = self._pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=self.chunk,
                    input_device_index=self.device_index,
                )
            except OSError:
                self._stream = self._pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=self.chunk,
                )

    def request_stop(self) -> None:
        self._stop_requested = True
        try:
            if self._stream and self._stream.is_active():
                self._stream.stop_stream()
        except Exception:
            pass

    def close(self) -> None:
        try:
            self._status.clear()
        except Exception:
            pass
        try:
            if self._stream:
                try:
                    if self._stream.is_active():
                        self._stream.stop_stream()
                except Exception:
                    pass
                self._stream.close()
        finally:
            self._stream = None
            if self._pa:
                self._pa.terminate()
                self._pa = None

    def _read_frame(self) -> np.ndarray:
        if self._stop_requested:
            raise StopIteration
        assert self._stream is not None
        data = self._stream.read(self.chunk, exception_on_overflow=False)
        if self._stop_requested:
            raise StopIteration
        return np.frombuffer(data, dtype=np.int16)

    @staticmethod
    def _clamp_floor(x: float) -> float:
        s = cfg.settings
        return max(s.vad_floor_min, min(s.vad_floor_max, x))

    def _update_ema(self, value: float, ema: float, alpha: float) -> float:
        return (alpha * ema) + ((1.0 - alpha) * value)

    def _threshold(self) -> float:
        s = cfg.settings
        return max(s.vad_threshold_abs, self.floor_rms * s.vad_threshold_mult)

    def _notify_recording(self, flag: bool) -> None:
        try:
            if self._on_recording is not None:
                self._on_recording(flag)
        except Exception:
            pass

    def calibrate(self, seconds: float = None) -> None:
        s = cfg.settings
        seconds = s.vad_calibration_sec if seconds is None else seconds
        n_frames = max(1, int((seconds * 1000) / self.frame_ms))
        floors = []
        for _ in range(n_frames):
            frame = self._read_frame()
            floors.append(_rms_int16(frame))
        base = float(np.percentile(floors, 10))
        self.floor_rms = self._clamp_floor(base)
        self.env_rms = self.floor_rms
        if cfg.settings.vad_log_transitions:
            p90 = float(np.percentile(floors, 90))
            p10 = float(np.percentile(floors, 10))
            log.info("📉 VAD calibrated | floor=%.1f RMS (p10=%.1f, p90=%.1f) thr≈%.1f",
                     self.floor_rms, p10, p90, self._threshold())

    def utterances(self) -> Generator[Tuple[np.ndarray, int], None, None]:
        s = cfg.settings
        pre_frames = max(0, int(s.vad_pre_roll_ms / self.frame_ms))
        prebuf: Deque[np.ndarray] = collections.deque(maxlen=pre_frames)

        attack_needed = max(1, int(s.vad_attack_ms / self.frame_ms))
        release_needed = max(1, int(s.vad_release_ms / self.frame_ms))
        hangover_frames = max(0, int(s.vad_hangover_ms / self.frame_ms))
        max_frames = int((s.vad_max_utterance_sec * 1000) / self.frame_ms)

        in_speech = False
        above_cnt = 0
        below_cnt = 0
        hangover = 0
        cur: list[np.ndarray] = []

        while True:
            if self._stop_requested:
                return

            frame = self._read_frame()
            self._frame_idx += 1
            prebuf.append(frame)

            r_inst = _rms_int16(frame)
            prev_thr = self._threshold()
            self.env_rms = self._update_ema(r_inst, self.env_rms, self.alpha_env)

            thr = self._threshold()
            is_above = (r_inst >= thr) if s.vad_use_instant_rms_for_trigger else (self.env_rms >= thr)

            if not in_speech and r_inst < (s.vad_floor_adapt_margin * thr):
                new_floor = self._update_ema(r_inst, self.floor_rms, self.alpha_floor)
                self.floor_rms = self._clamp_floor(new_floor)
                now = time.time()
                if s.vad_log_threshold_changes_ms > 0 and (now - self._last_thr_log_ts) * 1000 >= s.vad_log_threshold_changes_ms:
                    if abs(thr - prev_thr) >= 1.0:
                        log.info("↘️  idle | floor=%.1f env=%.1f thr≈%.1f", self.floor_rms, self.env_rms, thr)
                        self._last_thr_log_ts = now

            n = s.vad_log_stats_every_n_frames
            if n and (self._frame_idx % n == 0):
                log.debug("frame=%d | r=%.1f env=%.1f floor=%.1f thr≈%.1f %s",
                          self._frame_idx, r_inst, self.env_rms, self.floor_rms, thr,
                          "ABOVE" if is_above else "below")

            if not in_speech and s.vad_heartbeat_ms > 0:
                now = time.time()
                if (now - self._last_heartbeat_ts) * 1000 >= s.vad_heartbeat_ms:
                    self._status.update(
                        f"💤 idle | r={r_inst:.1f} env={self.env_rms:.1f} floor={self.floor_rms:.1f} thr≈{thr:.1f} (waiting)"
                    )
                    self._last_heartbeat_ts = now

            if not in_speech:
                above_cnt = above_cnt + 1 if is_above else 0
                if above_cnt >= attack_needed:
                    in_speech = True
                    self._notify_recording(True)
                    hangover = 0
                    cur = list(prebuf)
                    cur.append(frame)
                    below_cnt = 0
                    if s.vad_log_transitions:
                        self._status.clear()
                        log.info("▶️  START | r=%.1f ≥ thr≈%.1f | attack=%d frames | pre_roll=%d frames",
                                 r_inst, thr, attack_needed, len(prebuf))
                    continue
            else:
                cur.append(frame)
                if is_above:
                    below_cnt = 0
                    hangover = hangover_frames
                else:
                    below_cnt += 1
                    if hangover > 0:
                        hangover -= 1
                        below_cnt = 0

                stop_reason = None
                if below_cnt >= release_needed:
                    stop_reason = f"release {release_needed} frames"
                elif len(cur) >= max_frames:
                    stop_reason = f"max_len {max_frames} frames"

                if stop_reason is not None:
                    pcm = np.concatenate(cur) if cur else np.zeros(0, dtype=np.int16)
                    utt_ms = len(cur) * self.frame_ms

                    if s.vad_log_transitions:
                        try:
                            avg_rms = float(np.mean([_rms_int16(f) for f in cur]))
                            peak = int(np.max(np.abs(pcm))) if pcm.size else 0
                        except Exception:
                            avg_rms, peak = 0.0, 0
                        self._status.clear()
                        log.info("⏹ END  | %s | dur=%.0f ms frames=%d avgRMS=%.1f peak=%d thr≈%.1f",
                                 stop_reason, utt_ms, len(cur), avg_rms, peak, thr)

                    self._notify_recording(False)

                    if utt_ms >= s.vad_min_utterance_ms:
                        yield pcm, self.sample_rate
                    else:
                        if s.vad_log_transitions:
                            log.info("🪵 drop | too short (%d ms < %d ms)", int(utt_ms), int(s.vad_min_utterance_ms))

                    in_speech = False
                    above_cnt = 0
                    below_cnt = 0
                    hangover = 0
                    cur = []

    @staticmethod
    def _peak_normalize_int16(x: np.ndarray, target_dbfs: float) -> np.ndarray:
        if x.size == 0:
            return x
        peak = np.max(np.abs(x))
        if peak == 0:
            return x
        target_linear = 32767.0 * (10.0 ** (target_dbfs / 20.0))
        gain = target_linear / float(peak)
        y = np.clip(x.astype(np.float32) * gain, -32768.0, 32767.0).astype(np.int16)
        return y

    @staticmethod
    def write_wav(path: str, pcm: np.ndarray, sample_rate: int, normalize_dbfs: Optional[float]) -> None:
        y = pcm
        if normalize_dbfs is not None:
            y = NoiseGateVAD._peak_normalize_int16(y, normalize_dbfs)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(y.tobytes())
