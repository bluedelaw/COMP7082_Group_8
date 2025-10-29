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

# --- Voice shutdown intent handling (deterministic) ---------------------------
_SHUTDOWN_HOTWORDS = re.compile(
    r"\b("
    r"shut\s*down|shutdown|power\s*off|turn\s*off|stop\s+listening|stop\s+the\s+server|stop\s+server|"
    r"exit|quit|terminate|end\s+(?:session|process|server)|kill\s+(?:it|process|server)"
    r")\b",
    re.IGNORECASE,
)
_NEGATIONS = re.compile(r"\b(don't|do\s+not|not\s+now|cancel|false\s+alarm)\b", re.IGNORECASE)

# Optional confirmation hotwords (only used if VOICE_SHUTDOWN_CONFIRM=True)
_CONFIRM_HOTWORDS = re.compile(
    r"\b(confirm(?:ed)?\s+(?:shut\s*down|shutdown|exit|quit)|yes[, ]*(?:shut\s*down|exit)|go\s+ahead)\b",
    re.IGNORECASE,
)
_CONFIRM_WINDOW_SEC = 15.0


def _intent_shutdown(text: str) -> bool:
    if _NEGATIONS.search(text):
        return False
    return bool(_SHUTDOWN_HOTWORDS.search(text))


def _intent_confirm(text: str) -> bool:
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

    # If confirmation mode is enabled, track its window
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

            # Wait for next utterance
            try:
                pcm, sr = next(utter_gen)
            except StopIteration:
                return
            except Exception as e:
                if stop_event.is_set():
                    return
                log.exception("VAD stream error: %s", e)
                await asyncio.sleep(0.05)
                continue

            # Save utterance
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

            # ---------------- Voice shutdown logic ----------------
            if not cfg.VOICE_SHUTDOWN_CONFIRM:
                # Single-shot: immediate exit on hotword
                if _intent_shutdown(text):
                    log.info("🛑 Voice shutdown requested. Exiting immediately…")
                    await _hard_exit_after_cleanup(stop_event)
                    return  # not reached
            else:
                # Two-step confirmation mode
                now = time.monotonic()
                if pending_shutdown_deadline and now > pending_shutdown_deadline:
                    pending_shutdown_deadline = None

                if pending_shutdown_deadline is None:
                    if _intent_shutdown(text):
                        pending_shutdown_deadline = now + _CONFIRM_WINDOW_SEC
                        log.info(
                            "⚠️  Shutdown intent detected. Waiting up to %.0fs for confirmation "
                            "(say: 'confirm shutdown' or 'yes, shut down').",
                            _CONFIRM_WINDOW_SEC,
                        )
                        log.info("📣  [reply] To confirm shutdown, say: 'confirm shutdown'.")
                        try:
                            await asyncio.wait_for(stop_event.wait(), timeout=0.05)
                        except asyncio.TimeoutError:
                            pass
                        continue
                else:
                    if _intent_confirm(text):
                        log.info("🛑 Voice confirmation received. Shutting down now…")
                        await _hard_exit_after_cleanup(stop_event)
                        return

            # ---------------- Normal assistant reply ----------------
            log.info("🤖  [reply] generating response…")
            reply = generate_reply(text, cfg=cfg_ai)
            log.info("📣  [reply] %s", reply)

            # Metrics
            cycle_ms = int((time.perf_counter() - cycle_start) * 1000)
            log.info("⏱️  [cycle] done in %d ms\n", cycle_ms)

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
