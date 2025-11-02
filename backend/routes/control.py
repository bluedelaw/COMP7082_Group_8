# backend/routes/control.py
from __future__ import annotations

import asyncio
import logging
import os
from fastapi import APIRouter, Request

from backend.schemas import StatusResponse, SimpleMessage
from backend.listener import run_listener

log = logging.getLogger("jarvin.routes.control")

router = APIRouter(tags=["control"])


@router.get("/status", response_model=StatusResponse)
async def status(request: Request) -> StatusResponse:
    """
    Report whether the background listener task is running.
    """
    app = request.app
    running = getattr(app.state, "listener_task", None) is not None and not app.state.listener_task.done()
    return StatusResponse(listening=running)


@router.post("/start", response_model=SimpleMessage)
async def start_listener(request: Request) -> SimpleMessage:
    """
    Start the background listener task if it isn't already running.
    """
    app = request.app
    task = getattr(app.state, "listener_task", None)
    if task is not None and not task.done():
        return SimpleMessage(ok=True, message="Listener already running.")

    app.state.stop_event.clear()
    app.state.listener_task = asyncio.create_task(
        run_listener(app.state.stop_event, initial_delay=0.0)
    )
    log.info("Listener started via control API.")
    return SimpleMessage(ok=True, message="Listener started.")


@router.post("/stop", response_model=SimpleMessage)
async def stop_listener(request: Request) -> SimpleMessage:
    """
    Request the background listener task to stop.
    """
    app = request.app
    task = getattr(app.state, "listener_task", None)
    if task is None or task.done():
        return SimpleMessage(ok=True, message="Listener already stopped.")
    app.state.stop_event.set()
    log.info("Listener stop requested via control API.")
    return SimpleMessage(ok=True, message="Listener stopping...")


@router.post("/shutdown", response_model=SimpleMessage)
async def shutdown_server(request: Request) -> SimpleMessage:
    """
    Terminate the entire FastAPI + UI process. We set the stop_event to
    let the listener clean up, then exit the process shortly after
    returning a response (so the client gets HTTP 200).
    """
    app = request.app
    try:
        app.state.stop_event.set()
    except Exception:
        pass

    async def _exit_soon():
        # small delay so the HTTP response can flush
        await asyncio.sleep(0.15)
        os._exit(0)

    asyncio.create_task(_exit_soon())
    log.info("Shutdown requested via control API. Exiting process…")
    return SimpleMessage(ok=True, message="Server shutting down.")
