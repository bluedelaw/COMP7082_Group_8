# backend/main.py
from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

# Ensure package imports in dev
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from backend.logging_setup import init_logging
import config as cfg
from backend.listener import run_listener
from audio.speech_recognition import transcribe_audio
from backend.llm_bootstrap import provision_llm

# ----------------------------------------------------------------------------- #
# Centralized logging initialization (uses level from config.py)
# ----------------------------------------------------------------------------- #
init_logging(cfg.LOG_LEVEL)
log = logging.getLogger("jarvin")

# ----------------------------------------------------------------------------- #
# Lifespan: starts background tasks on boot, stops them on shutdown
# ----------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.stop_event = asyncio.Event()

    # Provision GGUF if enabled (llama.cpp path)
    if cfg.LLM_AUTO_PROVISION:
        try:
            await provision_llm()
        except Exception as e:
            log.exception("LLM provisioning failed: %s", e)

    # Start listener with small initial delay
    app.state.listener_task = asyncio.create_task(
        run_listener(app.state.stop_event, initial_delay=cfg.INITIAL_LISTENER_DELAY)
    )
    log.info("🎧 Listener task started automatically on server boot.")

    try:
        yield
    except (asyncio.CancelledError, KeyboardInterrupt):
        log.debug("Lifespan cancellation received during shutdown; suppressing exception.")
    except Exception as e:
        log.exception("Unhandled exception in lifespan: %s", e)
    finally:
        log.info("🛑 Shutting down listener…")
        app.state.stop_event.set()
        task = getattr(app.state, "listener_task", None)
        if task:
            with suppress(asyncio.CancelledError):
                await task
        log.info("✅ Listener stopped.")

# ----------------------------------------------------------------------------- #
# FastAPI app
# ----------------------------------------------------------------------------- #
app = FastAPI(title="Jarvin Local", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------------- #
# REST routes
# ----------------------------------------------------------------------------- #
@app.post("/transcribe")
async def transcribe_endpoint(audio_file: UploadFile = File(...)):
    log.info(f"📥 Received file: {audio_file.filename} ({audio_file.content_type})")
    os.makedirs(cfg.TEMP_DIR, exist_ok=True)
    file_location = os.path.join(cfg.TEMP_DIR, audio_file.filename)
    with open(file_location, "wb") as f:
        f.write(await audio_file.read())
    log.info("🧠 Running Whisper transcription (one-off)…")
    text = transcribe_audio(file_location)
    log.info(f"✅ Done. Text length: {len(text)}")
    return {"transcribed_text": text}

@app.get("/status")
async def status():
    running = app.state.listener_task is not None and not app.state.listener_task.done()
    return {"listening": running}

@app.post("/start")
async def start_listener():
    if app.state.listener_task is not None and not app.state.listener_task.done():
        return {"ok": True, "message": "Listener already running."}
    app.state.stop_event.clear()
    app.state.listener_task = asyncio.create_task(
        run_listener(app.state.stop_event, initial_delay=0.0)
    )
    return {"ok": True, "message": "Listener started."}

@app.post("/stop")
async def stop_listener():
    if app.state.listener_task is None or app.state.listener_task.done():
        return {"ok": True, "message": "Listener already stopped."}
    app.state.stop_event.set()
    return {"ok": True, "message": "Listener stopping..."}
