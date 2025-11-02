# backend/routes/live.py
from __future__ import annotations

from fastapi import APIRouter
from backend.live_state import get_snapshot

router = APIRouter(tags=["live"])

@router.get("/live")
async def live_latest() -> dict:
    """
    Latest listener snapshot. Returns empty fields before the first utterance.
    Includes:
      - transcript, reply, utter_ms, cycle_ms, wav_path
      - recording (bool): true while VAD is inside an active speech segment
    """
    return get_snapshot()
