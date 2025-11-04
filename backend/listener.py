# backend/listener.py
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

import config as cfg
from audio.mic import get_default_input_device_index
from audio.speech_recognition import get_cached_model_and_device
from backend.ai_engine import JarvinConfig
from backend.intent import intent_shutdown, intent_confirm, CONFIRM_WINDOW_SEC
from backend.live_state import set_snapshot, set_status
from backend.audio_loop import AudioLoop
from backend.pipeline import process_utterance

log = logging.getLogger("jarvin")


async def _watch_stop_event(stop_event: asyncio.Event, loop: AudioLoop) -> None:
    await stop_event.wait()
    try:
        loop.request_stop()
    except Exception:
        pass


async def _hard_exit_after_cleanup(stop_event: asyncio.Event, delay_sec: float = 0.15) -> None:
    try:
        stop_event.set()
        await asyncio.sleep(delay_sec)
    finally:
        os._exit(0)


async def run_listener(stop_event: asyncio.Event, initial_delay: float = 0.2) -> None:
    s = cfg.settings

    # optional initial delay (for boot sequencing)
    if initial_delay > 0:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=initial_delay)
            return
        except asyncio.TimeoutError:
            pass

    # Whisper model warmup (single cached instance)
    model, device = get_cached_model_and_device(cfg.settings.whisper_model_size)
    log.info("🧠 Whisper ready | device=%s", device)

    # Mic device selection
    try:
        device_index: Optional[int] = get_default_input_device_index()
    except Exception as e:
        log.exception("No input device available: %s", e)
        device_index = None

    cfg_ai = JarvinConfig()
    pending_shutdown_deadline: Optional[float] = None

    def _on_recording(flag: bool) -> None:
        set_status(recording=flag)

    audio = AudioLoop(
        sample_rate=s.sample_rate,
        chunk=s.chunk,
        device_index=device_index,
        on_recording=_on_recording,
    )
    stopper_task: Optional[asyncio.Task] = None

    try:
        set_status(recording=False, processing=False)
        with audio:
            stopper_task = asyncio.create_task(_watch_stop_event(stop_event, audio))

            log.info(
                "🎧 Microphone stream opened (chunk=%d, ~%dms/frame).",
                s.chunk,
                int((s.chunk / s.sample_rate) * 1000),
            )
            log.info("⚙️  Calibrating noise floor for %.1fs…", s.vad_calibration_sec)
            await asyncio.to_thread(audio.calibrate, s.vad_calibration_sec)

            utter_gen = audio.utterances()
            while not stop_event.is_set():
                cycle_t0 = time.perf_counter()
                try:
                    pcm, sr = await asyncio.to_thread(next, utter_gen)
                except StopIteration:
                    return
                except Exception as e:
                    if stop_event.is_set():
                        return
                    log.exception("VAD stream error: %s", e)
                    await asyncio.sleep(0.05)
                    continue

                set_status(processing=True)

                # ---- process utterance (ASR + LLM) ----
                text, reply, tms, wav_path = await asyncio.to_thread(
                    process_utterance,
                    pcm,
                    sr,
                    model=model,
                    device=device,
                    cfg_ai=cfg_ai,
                )

                # ---- voice shutdown intents (orchestrator keeps this, pipeline stays pure) ----
                if not s.voice_shutdown_confirm:
                    if text and intent_shutdown(text):
                        log.info("🛑 Voice shutdown requested. Exiting immediately…")
                        set_status(processing=False)
                        await _hard_exit_after_cleanup(stop_event)
                        return
                else:
                    now = time.monotonic()
                    if pending_shutdown_deadline and now > pending_shutdown_deadline:
                        pending_shutdown_deadline = None
                    if pending_shutdown_deadline is None:
                        if text and intent_shutdown(text):
                            pending_shutdown_deadline = now + CONFIRM_WINDOW_SEC
                            log.info(
                                "⚠️  Shutdown intent detected. Waiting up to %.0fs for confirmation.",
                                CONFIRM_WINDOW_SEC,
                            )
                            set_snapshot(
                                transcript=text,
                                reply="To confirm shutdown, say: 'confirm shutdown'.",
                                cycle_ms=None,
                                utter_ms=tms.get("utter_ms"),
                                wav_path=wav_path,
                            )
                            set_status(processing=False)
                            try:
                                await asyncio.wait_for(stop_event.wait(), timeout=0.05)
                            except asyncio.TimeoutError:
                                pass
                            continue
                    else:
                        if text and intent_confirm(text):
                            log.info("🛑 Voice confirmation received. Shutting down now…")
                            set_status(processing=False)
                            await _hard_exit_after_cleanup(stop_event)
                            return

                # ---- publish snapshot ----
                cycle_ms = int((time.perf_counter() - cycle_t0) * 1000)
                if text:
                    log.info("📝  [result] “%s” (ASR %d ms)", text, tms.get("transcribe_ms", 0))
                else:
                    log.info("📝  [result] (empty) in %d ms", tms.get("transcribe_ms", 0))

                if reply:
                    log.info("📣  [reply] %s", reply)
                log.info("⏱️  [cycle] done in %d ms\n", cycle_ms)

                set_snapshot(
                    transcript=text if text else None,
                    reply=reply if reply else None,
                    cycle_ms=cycle_ms,
                    utter_ms=tms.get("utter_ms"),
                    wav_path=wav_path,
                )

                set_status(processing=False)

                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=0.05)
                except asyncio.TimeoutError:
                    pass

    except asyncio.CancelledError:
        return
    finally:
        try:
            if stopper_task:
                stopper_task.cancel()
        except Exception:
            pass
        set_status(recording=False, processing=False)
