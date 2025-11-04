# backend/pipeline.py
from __future__ import annotations

import time
from typing import Optional, Tuple, Dict

import numpy as np

import config as cfg
from backend.core.ports import ASRTranscriber, LLMChatEngine, AudioSink
from audio.wav_io import write_wav_int16_mono as _write_wav_int16_mono
from backend.util.paths import temp_path
from backend.ai_engine import JarvinConfig
from backend.asr.whisper import WhisperASR
from backend.llm.runtime_local import LocalChat


class _FnSink:
    """Default AudioSink that delegates to existing WAV writer."""
    @staticmethod
    def write_wav(path: str, pcm: np.ndarray, sample_rate: int, normalize_dbfs: float | None) -> None:
        _write_wav_int16_mono(path, pcm, sample_rate, normalize_dbfs)


def process_utterance(
    pcm: np.ndarray,
    sr: int,
    *,
    # ---- old-style params (still supported) ----
    model=None,
    device: str = "cpu",
    cfg_ai: Optional[JarvinConfig] = None,
    # ---- new-style ports (preferred going forward) ----
    asr: Optional[ASRTranscriber] = None,
    llm: Optional[LLMChatEngine] = None,
    audio_sink: Optional[AudioSink] = None,
) -> Tuple[str, str, Dict[str, int], str]:
    """
    Transcribe + generate reply for one utterance. Writes a temp wav (normalized if configured)
    and returns (text, reply, timings_ms, wav_path).

    Backward compatible:
      - If `asr`/`llm` are not provided, we construct adapters that preserve current behavior,
        using the globally cached Whisper and generate_reply().
      - `model`/`device` are still accepted to honor existing callers.
    """
    s = cfg.settings
    cfg_ai = cfg_ai or JarvinConfig()

    # Persist one temp wav for debugging/UI
    wav_path = temp_path("live_utt.wav")
    sink = audio_sink or _FnSink()
    sink.write_wav(wav_path, pcm, sr, s.normalize_to_dbfs)

    utt_ms = int((len(pcm) / max(1, sr)) * 1000)

    # New preferred path: adapter seam
    if asr is None:
        # If caller passed a whisper model/device explicitly (old style), reuse it by creating a tiny adapter.
        if model is not None:
            class _LegacyASR:
                def transcribe(self, path: str) -> str:
                    from audio.speech_recognition import transcribe_audio as _t
                    return _t(path, model=model, device=device)
            asr = _LegacyASR()
        else:
            asr = WhisperASR(s.whisper_model_size)

    if llm is None:
        class _LLMWithCfg:
            def __init__(self, base: LocalChat, cfg_ai: JarvinConfig) -> None:
                self._base = base
                self._cfg = cfg_ai
            def reply(self, user_text: str) -> str:
                # generate_reply already takes cfg when called directly, but our adapter uses LocalChat,
                # so just call the function to honor cfg_ai when it differs from default.
                from backend.ai_engine import generate_reply as _gen
                return _gen(user_text, cfg=self._cfg)

        llm = _LLMWithCfg(LocalChat(), cfg_ai)

    t0 = time.perf_counter()
    text = asr.transcribe(wav_path).strip()
    t_trans_ms = int((time.perf_counter() - t0) * 1000)

    reply = ""
    t_reply_ms = 0
    if text:
        t1 = time.perf_counter()
        reply = llm.reply(text) or ""
        t_reply_ms = int((time.perf_counter() - t1) * 1000)

    timings = {
        "utter_ms": utt_ms,
        "transcribe_ms": t_trans_ms,
        "reply_ms": t_reply_ms,
    }
    return text, reply, timings, wav_path
