# backend/app.py
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config as cfg
from backend.listener import run_listener
from backend.llm_bootstrap import provision_llm
from backend.routes.transcription import router as transcription_router
from backend.routes.control import router as control_router
from backend.routes.health import router as health_router
from backend.routes.chat import router as chat_router  # NEW
from backend.routes.live import router as live_router   # NEW

log = logging.getLogger("jarvin")

@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.stop_event = asyncio.Event()

    if cfg.LLM_AUTO_PROVISION:
        try:
            await provision_llm()
        except Exception as e:
            log.exception("LLM provisioning failed: %s", e)

    # Start listener conditionally based on config
    app.state.listener_task = None
    if cfg.START_LISTENER_ON_BOOT:
        app.state.listener_task = asyncio.create_task(
            run_listener(app.state.stop_event, initial_delay=cfg.INITIAL_LISTENER_DELAY)
        )
        log.info("🎧 Listener task started automatically on server boot.")
    else:
        log.info("🟡 START_LISTENER_ON_BOOT is False — server starts deaf; use /start to begin listening.")

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

def create_app() -> FastAPI:
    app = FastAPI(title="Jarvin Local", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(transcription_router)
    app.include_router(control_router)
    app.include_router(chat_router)  # NEW
    app.include_router(live_router)  # NEW

    return app
