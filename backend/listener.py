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


async def run_listener(stop_event: asyncio.Event, initial_delay: float = 0.2) -> None:
    """
    Background loop: record every N seconds, transcribe, generate reply.
    Terminates when stop_event is set.

    initial_delay: small delay to allow uvicorn to print "Application startup complete"
                   before the first recording/transcription logs.
    """
    # Optional initial delay to ensure startup logs from uvicorn appear first
    # Value is wired from config in backend/main.py
    if initial_delay > 0:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=initial_delay)
            return  # stop requested during initial delay
        except asyncio.TimeoutError:
            pass

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
                transcribe_ms = int((time.perf_counter() - t0) * 1000)

                if not text:
                    log.info("📝  [result] (empty) in %d ms", transcribe_ms)
                    # Normal idle wait: time out frequently; not an error.
                    try:
                        await asyncio.wait_for(stop_event.wait(), timeout=0.2)
                    except asyncio.TimeoutError:
                        pass
                    continue

                log.info("📝  [result] “%s” (%d ms)", text, transcribe_ms)

                # PHASE 3: REPLY
                log.info("🤖  [reply] generating response…")
                reply = generate_reply(text, cfg=cfg_ai)
                log.info("📣  [reply] %s", reply)

                cycle_ms = int((time.perf_counter() - cycle_start) * 1000)
                log.info("⏱️  [cycle] done in %d ms\n", cycle_ms)

            except asyncio.CancelledError:
                # Silent, expected during shutdown
                return
            except Exception as e:
                # Log and continue loop
                log.exception("Listener iteration failed: %s", e)

            # Small cooperative pause: wake early if stop_event is set; ignore normal timeouts.
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=0.2)
            except asyncio.TimeoutError:
                pass

    except asyncio.CancelledError:
        # Graceful cancellation
        return
