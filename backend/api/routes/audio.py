# backend/api/routes/audio.py
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from audio.mic import list_input_devices, get_default_input_device_index, set_default_input_device_index
from backend.listener.runner import run_listener

log = logging.getLogger("jarvin.routes.audio")
router = APIRouter(tags=["audio"])

class DevicesResponse(BaseModel):
    devices: list[dict]
    selected_index: Optional[int]
    selected_name: Optional[str]

class SelectRequest(BaseModel):
    index: int
    restart: bool = True

class SelectResponse(BaseModel):
    ok: bool
    selected_index: Optional[int]
    selected_name: Optional[str]
    message: str | None = None

@router.get("/audio/devices", response_model=DevicesResponse)
async def get_devices() -> DevicesResponse:
    devs = list_input_devices()
    try:
        sel_idx = get_default_input_device_index()
    except Exception:
        sel_idx = None

    sel_name = None
    if sel_idx is not None:
        for i, n in devs:
            if i == sel_idx:
                sel_name = n
                break

    return DevicesResponse(
        devices=[{"index": i, "name": n} for i, n in devs],
        selected_index=sel_idx,
        selected_name=sel_name,
    )

@router.post("/audio/select", response_model=SelectResponse)
async def select_device(payload: SelectRequest, request: Request) -> SelectResponse:
    # Set the cached default first so a restart will pick it up
    # (runner calls get_default_input_device_index() on open)
    devs = dict(list_input_devices())
    name = devs.get(payload.index)
    set_default_input_device_index(payload.index, name)

    if payload.restart:
        app = request.app
        # stop if running
        task = getattr(app.state, "listener_task", None)
        if task is not None and not task.done():
            app.state.stop_event.set()
            log.info("Stopping listener to apply new input device…")
            try:
                with asyncio.timeout(2.5):
                    await task
            except Exception:
                pass
            app.state.stop_event.clear()
        # start again with new default
        app.state.listener_task = asyncio.create_task(run_listener(app.state.stop_event, initial_delay=0.0))
        log.info("Listener restarted with input device [%d] %s", payload.index, name or "")

    return SelectResponse(ok=True, selected_index=payload.index, selected_name=name, message="applied")
