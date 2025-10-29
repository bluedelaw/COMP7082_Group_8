# backend/listener.py
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Optional

import config as cfg
from audio.mic import load_whisper_model, get_default_input_device_index
from audio.vad import NoiseGateVAD
from audio.speech_recognition import transcribe_audio
from backend.ai_engine import generate_reply, JarvinConfig

log = logging.getLogger("jarvin")

# --- Voice shutdown intent handling ------------------------------------------
# Deterministic keywords (fast, reliable)
_SHUTDOWN_HOTWORDS = re.compile(
    r"\b("
    r"shut\s*down|shutdown|power\s*off|turn\s*off|stop\s+listening|stop\s+the\s+server|stop\s+server|"
    r"exit|quit|terminate|kill\s+(?:it|process|server)|end\s+(?:session|process|server)"
    r")\b",
    re.IGNORECASE,
)
# Explicit confirm words
_CONFIRM_HOTWORDS = re.compile(
    r"\b(confirm(?:ed)?\s+(?:shut\s*down|shutdown|exit|quit)|yes[, ]*(?:shut\s*down|exit)|go\s+ahead)\b",
    re.IGNORECASE,
)
# Common negations to avoid accidental exits
_NEGATIONS = re.compile(r"\b(don't|do\s+not|not\s+now|cancel|false\s+alarm)\b", re.IGNORECASE)

_CONFIRM_WINDOW_SEC = 15.0  # time allowed to say the confirmation phrase


def _intent_shutdown(text: str) -> bool:
    """Return True if the text strongly looks like a shutdown request."""
    if _NEGATIONS.search(text):
        return False
    return bool(_SHUTDOWN_HOTWORDS.search(text))


def _intent_confirm(text: str) -> bool:
    """Return True if the text clearly confirms shutdown."""
    if _NEGATIONS.search(text):
        return False
    return bool(_CONFIRM_HOTWORDS.search(text))


def _temp_wav_path(kind: str = "utt") -> str:
    os.makedirs(cfg.TEMP_DIR, exist_ok=True)
    return os.path.join(cfg.TEMP_DIR, f"{kind}.wav")


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
    We therefore do a deliberate, clean-ish shutdown:
      - signal listener stop
      - small async delay to let tasks unwind
      - hard-exit process (os._exit) to ensure Uvicorn terminates
    """
    try:
        stop_event.set()
        await asyncio.sleep(delay_sec)
    finally:
        os._exit(0)  # hard exit avoids uvicorn event-loop quirks on Windows


async def run_listener(stop_event: asyncio.Event, initial_delay: float = 0.2) -> None:
    """
    Stream listener:
      - calibrates noise floor
      - yields utterances on dynamic changes
      - transcribes & replies
      - supports voice-initiated shutdown with explicit confirmation
      - immediate shutdown path for Windows via os._exit(0)
    """
    if initial_delay > 0:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=initial_delay)
            return
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

    # Shutdown confirmation state
    pending_shutdown_deadline: Optional[float] = None

    vad = NoiseGateVAD(sample_rate=cfg.SAMPLE_RATE, chunk=cfg.CHUNK, device_index=device_index)
    stopper_task: Optional[asyncio.Task] = None

    try:
        vad.open()
        stopper_task = asyncio.create_task(_watch_stop_event(stop_event, vad))

        log.info("🎧 Microphone stream opened (chunk=%d, ~%dms/frame).",
                 cfg.CHUNK, int((cfg.CHUNK / cfg.SAMPLE_RATE) * 1000))
        log.info("⚙️  Calibrating noise floor for %.1fs…", cfg.VAD_CALIBRATION_SEC)
        vad.calibrate(cfg.VAD_CALIBRATION_SEC)
        log.info("📉 Initial floor RMS=%.1f, threshold≈%.1f", vad.floor_rms, vad._threshold())

        utter_gen = vad.utterances()
        while not stop_event.is_set():
            cycle_start = time.perf_counter()

            # Block until an utterance is yielded (PyAudio.read is unblocked by stopper_task)
            try:
                pcm, sr = next(utter_gen)
            except StopIteration:
                # Stop requested; exit cleanly
                return
            except Exception as e:
                if stop_event.is_set():
                    return
                log.exception("VAD stream error: %s", e)
                await asyncio.sleep(0.05)
                continue

            # Persist utterance to a temp wav (with optional normalization)
            wav_path = _temp_wav_path("live_utt")
            NoiseGateVAD.write_wav(wav_path, pcm, sr, normalize_dbfs=cfg.NORMALIZE_TO_DBFS)
            log.info("💾 saved utterance → %s", wav_path)

            if stop_event.is_set():
                return

            # Transcribe
            t0 = time.perf_counter()
            log.info("🧠  [transcribe] utterance… (len=%.2fs)", len(pcm) / sr)
            text = transcribe_audio(wav_path, model=model, device=device).strip()
            t_ms = int((time.perf_counter() - t0) * 1000)

            if not text:
                log.info("📝  [result] (empty) in %d ms", t_ms)
                continue

            log.info("📝  [result] “%s” (%d ms)", text, t_ms)

            # ------------ Voice shutdown flow ------------
            now = time.monotonic()

            # Expire any stale pending confirmation window
            if pending_shutdown_deadline is not None and now > pending_shutdown_deadline:
                pending_shutdown_deadline = None

            if pending_shutdown_deadline is None:
                # First stage: detect shutdown intent
                if _intent_shutdown(text):
                    pending_shutdown_deadline = now + _CONFIRM_WINDOW_SEC
                    log.info(
                        "⚠️  Shutdown intent detected. Waiting up to %.0fs for confirmation "
                        "(say: 'confirm shutdown' or 'yes, shut down').",
                        _CONFIRM_WINDOW_SEC,
                    )
                    # Optional: produce a short confirmation prompt (no LLM round-trip)
                    log.info("📣  [reply] To confirm shutdown, say: 'confirm shutdown'.")
                    # Small cooperative pause so the hint isn't immediately swallowed by next capture
                    try:
                        await asyncio.wait_for(stop_event.wait(), timeout=0.05)
                    except asyncio.TimeoutError:
                        pass
                    continue
            else:
                # Second stage: require explicit confirmation
                if _intent_confirm(text):
                    log.info("🛑 Voice confirmation received. Shutting down now…")
                    await _hard_exit_after_cleanup(stop_event)
                    return  # not reached
                else:
                    # If user spoke something else within the window but not confirm, keep listening
                    pass

            # ------------ Normal assistant reply ------------
            log.info("🤖  [reply] generating response…")
            reply = generate_reply(text, cfg=cfg_ai)
            log.info("📣  [reply] %s", reply)

            cycle_ms = int((time.perf_counter() - cycle_start) * 1000)
            log.info("⏱️  [cycle] done in %d ms\n", cycle_ms)

            # Small cooperative pause
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
        try:
            vad.request_stop()
        except Exception:
            pass
        try:
            vad.close()
        except Exception:
            pass
