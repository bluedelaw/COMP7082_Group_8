# backend/listener.py
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

import config as cfg
from audio.mic import get_default_input_device_index
from audio.vad import NoiseGateVAD
from audio.speech_recognition import transcribe_audio, get_cached_model_and_device
from audio.wav_io import write_wav_int16_mono
from backend.ai_engine import generate_reply, JarvinConfig
from backend.intent import intent_shutdown, intent_confirm, CONFIRM_WINDOW_SEC
from backend.util.paths import temp_path
from backend.live_state import set_snapshot, set_status  # UPDATED

log = logging.getLogger("jarvin")


async def _watch_stop_event(stop_event: asyncio.Event, vad: NoiseGateVAD) -> None:
    """As soon as stop_event is set, immediately unblock PyAudio.read()."""
    await stop_event.wait()
    try:
        vad.request_stop()
    except Exception:
        pass


async def _hard_exit_after_cleanup(stop_event: asyncio.Event, delay_sec: float = 0.15) -> None:
    """
    On Windows with Uvicorn, Ctrl+C may not propagate while PyAudio is active.
    Do a deliberate, clean-ish shutdown then hard-exit.
    """
    try:
        stop_event.set()
        await asyncio.sleep(delay_sec)
    finally:
        os._exit(0)  # ensures immediate termination


async def run_listener(stop_event: asyncio.Event, initial_delay: float = 0.2) -> None:
    """
    Stream listener with noise-gated VAD:
      - calibrates noise floor and captures utterances
      - transcribes & replies
      - voice-initiated shutdown (single-shot by default; configurable)

    IMPORTANT: All blocking CPU-bound work (PyAudio/VAD iteration, Whisper, LLM)
    is offloaded to threads via asyncio.to_thread so the event loop remains free
    to serve HTTP/Gradio UI.
    """
    if initial_delay > 0:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=initial_delay)
            return
        except asyncio.TimeoutError:
            pass

    # Unified ASR model lifecycle (shared with API)
    model, device = get_cached_model_and_device(None)
    log.info("🧠 Whisper ready | device=%s", device)

    # Cache device index once
    try:
        device_index: Optional[int] = get_default_input_device_index()
    except Exception as e:
        log.exception("No input device available: %s", e)
        device_index = None

    cfg_ai = JarvinConfig()

    # If confirmation mode is enabled, track its window
    pending_shutdown_deadline: Optional[float] = None

    # Hook to surface “recording” state to the UI in real-time
    def _on_recording(flag: bool) -> None:
        set_status(recording=flag)

    vad = NoiseGateVAD(
        sample_rate=cfg.SAMPLE_RATE,
        chunk=cfg.CHUNK,
        device_index=device_index,
        on_recording=_on_recording,  # NEW
    )
    stopper_task: Optional[asyncio.Task] = None

    try:
        # Ensure UI flags are clean before entering the stream
        set_status(recording=False, processing=False)

        # Use context manager to guarantee resource cleanup
        with vad:
            stopper_task = asyncio.create_task(_watch_stop_event(stop_event, vad))

            log.info(
                "🎧 Microphone stream opened (chunk=%d, ~%dms/frame).",
                cfg.CHUNK,
                int((cfg.CHUNK / cfg.SAMPLE_RATE) * 1000),
            )
            log.info("⚙️  Calibrating noise floor for %.1fs…", cfg.VAD_CALIBRATION_SEC)

            # Calibration reads frames synchronously; run in a thread
            await asyncio.to_thread(vad.calibrate, cfg.VAD_CALIBRATION_SEC)
            log.info("📉 Initial floor RMS=%.1f, threshold≈%.1f", vad.floor_rms, vad._threshold())

            utter_gen = vad.utterances()
            while not stop_event.is_set():
                cycle_start = time.perf_counter()

                # Wait for next utterance — advance the generator in a thread
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

                # Save utterance (I/O handled by wav_io; cheap)
                wav_path = temp_path("live_utt.wav")
                write_wav_int16_mono(wav_path, pcm, sr, normalize_dbfs=cfg.NORMALIZE_TO_DBFS)
                log.info("💾 saved utterance → %s", wav_path)

                # We just transitioned from recording -> not recording.
                # The system is now busy transcribing/LLM; reflect that to UI.
                set_status(processing=True)

                if stop_event.is_set():
                    set_status(processing=False)
                    return

                # Transcribe (Whisper is CPU/GPU-bound) — run in a thread
                t0 = time.perf_counter()
                utt_len_sec = len(pcm) / sr
                log.info("🧠  [transcribe] utterance… (len=%.2fs)", utt_len_sec)
                text = (await asyncio.to_thread(transcribe_audio, wav_path, model, device)).strip()
                t_ms = int((time.perf_counter() - t0) * 1000)

                if not text:
                    log.info("📝  [result] (empty) in %d ms", t_ms)
                    # Publish snapshot even if empty transcript (keeps UI aligned)
                    set_snapshot(
                        transcript=None,
                        reply=None,
                        cycle_ms=None,
                        utter_ms=int(utt_len_sec * 1000),
                        wav_path=wav_path,
                    )
                    # Done processing this (empty) turn
                    set_status(processing=False)
                    continue

                log.info("📝  [result] “%s” (%d ms)", text, t_ms)

                # ---------------- Voice shutdown logic ----------------
                if not cfg.VOICE_SHUTDOWN_CONFIRM:
                    # Single-shot: immediate exit on hotword
                    if intent_shutdown(text):
                        log.info("🛑 Voice shutdown requested. Exiting immediately…")
                        # Ensure we drop processing flag before exit
                        set_status(processing=False)
                        await _hard_exit_after_cleanup(stop_event)
                        return  # not reached
                else:
                    # Two-step confirmation mode
                    now = time.monotonic()
                    if pending_shutdown_deadline and now > pending_shutdown_deadline:
                        pending_shutdown_deadline = None

                    if pending_shutdown_deadline is None:
                        if intent_shutdown(text):
                            pending_shutdown_deadline = now + CONFIRM_WINDOW_SEC
                            log.info(
                                "⚠️  Shutdown intent detected. Waiting up to %.0fs for confirmation "
                                "(say: 'confirm shutdown' or 'yes, shut down').",
                                CONFIRM_WINDOW_SEC,
                            )
                            log.info("📣  [reply] To confirm shutdown, say: 'confirm shutdown'.")
                            try:
                                await asyncio.wait_for(stop_event.wait(), timeout=0.05)
                            except asyncio.TimeoutError:
                                pass
                            # Prompt user; still processing ends here
                            set_snapshot(
                                transcript=text,
                                reply="To confirm shutdown, say: 'confirm shutdown'.",
                                cycle_ms=None,
                                utter_ms=int(utt_len_sec * 1000),
                                wav_path=wav_path,
                            )
                            set_status(processing=False)
                            continue
                    else:
                        if intent_confirm(text):
                            log.info("🛑 Voice confirmation received. Shutting down now…")
                            set_status(processing=False)
                            await _hard_exit_after_cleanup(stop_event)
                            return

                # ---------------- Normal assistant reply ----------------
                log.info("🤖  [reply] generating response…")
                # LLM generation is blocking; run in a thread
                reply = await asyncio.to_thread(generate_reply, text, cfg_ai)
                log.info("📣  [reply] %s", reply)

                # Metrics
                cycle_ms = int((time.perf_counter() - cycle_start) * 1000)
                log.info("⏱️  [cycle] done in %d ms\n", cycle_ms)

                # Publish a snapshot for the UI
                set_snapshot(
                    transcript=text if text else None,
                    reply=reply if reply else None,
                    cycle_ms=cycle_ms,
                    utter_ms=int(utt_len_sec * 1000),
                    wav_path=wav_path,
                )

                # Done processing for this turn
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
        # ensure UI doesn't stay “recording/processing” if we exit mid-utterance
        set_status(recording=False, processing=False)
