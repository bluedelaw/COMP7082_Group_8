# backend/listener.py
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import config as cfg
from audio.mic import (
    load_whisper_model,
    record_and_prepare_chunk,
    get_default_input_device_index,
)
from audio.speech_recognition import transcribe_audio
from backend.ai_engine import generate_reply, JarvinConfig

log = logging.getLogger("jarvin")


async def run_listener(stop_event: asyncio.Event) -> None:
    """
    Background loop: record every N seconds, transcribe, generate reply.
    Terminates when stop_event is set.
    """
    model, device, model_size = load_whisper_model()
    log.info(f"🧠 Whisper ready | size={model_size}, device={device}")

    # Cache device index once
    try:
        device_index: Optional[int] = get_default_input_device_index()
    except Exception as e:
        log.exception("No input device available: %s", e)
        device_index = None

    cfg_ai = JarvinConfig()

    try:
        while not stop_event.is_set():
            cycle_start = time.perf_counter()

            try:
                # PHASE 1: RECORDING
                log.info("🎙️  [recording] listening for %ss…", cfg.RECORD_SECONDS)
                wav = record_and_prepare_chunk(
                    basename="chunk",
                    seconds=cfg.RECORD_SECONDS,
                    amp_factor=cfg.AMP_FACTOR,
                    device_index=device_index,
                )

                # PHASE 2: TRANSCRIBING
                t0 = time.perf_counter()
                log.info("🧠  [transcribe] running Whisper…")
                text = transcribe_audio(wav, model=model, device=device).strip()
                t1 = time.perf_counter()
                transcribe_ms = int((t1 - t0) * 1000)

                if not text:
                    log.info("📝  [result] (empty) in %d ms", transcribe_ms)
                    await asyncio.wait_for(stop_event.wait(), timeout=0.2)
                    continue

                log.info("📝  [result] “%s” (%d ms)", text, transcribe_ms)

                # PHASE 3: REPLY
                log.info("🤖  [reply] generating response…")
                reply = generate_reply(text, cfg=cfg_ai)
                log.info("📣  [reply] %s", reply)

                cycle_ms = int((time.perf_counter() - cycle_start) * 1000)
                log.info("⏱️  [cycle] done in %d ms\n", cycle_ms)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.exception("Listener iteration failed: %s", e)

            # Small cooperative pause
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=0.2)
            except asyncio.TimeoutError:
                pass

    except asyncio.CancelledError:
        pass  # Graceful cancellation
