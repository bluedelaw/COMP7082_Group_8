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

log = logging.getLogger("jarvin")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """
    Lifespan manager: provisions the LLM (optional) and starts/stops the listener task.
    No logging initialization here (caller/launcher handles that).
    """
    app.state.stop_event = asyncio.Event()

    if cfg.LLM_AUTO_PROVISION:
        try:
            await provision_llm()
        except Exception as e:
            log.exception("LLM provisioning failed: %s", e)

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


def create_app() -> FastAPI:
    """
    App factory: builds and returns a FastAPI app wired with middleware, routes, and lifespan.
    Keeping construction side-effect free improves modularity and testability.
    """
    app = FastAPI(title="Jarvin Local", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount route modules
    app.include_router(health_router)
    app.include_router(transcription_router)
    app.include_router(control_router)

    return app
