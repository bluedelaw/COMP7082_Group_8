# backend/pipeline.py
from __future__ import annotations

import time
from typing import Optional, Tuple, Dict

import numpy as np

import config as cfg
from audio.speech_recognition import transcribe_audio
from audio.wav_io import write_wav_int16_mono
from backend.ai_engine import generate_reply, JarvinConfig
from backend.util.paths import temp_path


def process_utterance(
    pcm: np.ndarray,
    sr: int,
    *,
    model=None,
    device: str = "cpu",
    cfg_ai: Optional[JarvinConfig] = None,
) -> Tuple[str, str, Dict[str, int], str]:
    """
    Transcribe + generate reply for one utterance. Writes a temp wav (normalized if configured)
    and returns (text, reply, timings_ms, wav_path).

    timings_ms: {
      "utter_ms": <duration of utterance>,
      "transcribe_ms": ...,
      "reply_ms": ...
    }
    """
    s = cfg.settings
    cfg_ai = cfg_ai or JarvinConfig()

    # Persist one temp wav for debugging/UI
    wav_path = temp_path("live_utt.wav")
    write_wav_int16_mono(wav_path, pcm, sr, normalize_dbfs=s.normalize_to_dbfs)

    utt_ms = int((len(pcm) / max(1, sr)) * 1000)

    t0 = time.perf_counter()
    text = transcribe_audio(wav_path, model=model, device=device).strip()
    t_trans_ms = int((time.perf_counter() - t0) * 1000)

    reply = ""
    t_reply_ms = 0
    if text:
        t1 = time.perf_counter()
        reply = generate_reply(text, cfg=cfg_ai) or ""
        t_reply_ms = int((time.perf_counter() - t1) * 1000)

    timings = {
        "utter_ms": utt_ms,
        "transcribe_ms": t_trans_ms,
        "reply_ms": t_reply_ms,
    }
    return text, reply, timings, wav_path
