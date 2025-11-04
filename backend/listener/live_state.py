# backend/listener/live_state.py
from __future__ import annotations
import threading
from typing import Any, Dict, Optional
import time

_lock = threading.Lock()
_state: Dict[str, Any] = {
    "ts": None,
    "utter_ms": None,
    "transcript": None,
    "reply": None,
    "cycle_ms": None,
    "wav_path": None,
    "recording": False,
    "processing": False,
}

def set_snapshot(*, transcript: Optional[str], reply: Optional[str],
                 cycle_ms: Optional[int], utter_ms: Optional[int],
                 wav_path: Optional[str]) -> None:
    with _lock:
        _state.update({
            "ts": time.monotonic(),
            "transcript": transcript,
            "reply": reply,
            "cycle_ms": cycle_ms,
            "utter_ms": utter_ms,
            "wav_path": wav_path,
        })

def set_status(*, recording: Optional[bool] = None, processing: Optional[bool] = None) -> None:
    if recording is None and processing is None:
        return
    with _lock:
        if recording is not None:
            _state["recording"] = bool(recording)
        if processing is not None:
            _state["processing"] = bool(processing)
        _state["ts"] = time.monotonic()

def get_snapshot() -> Dict[str, Any]:
    with _lock:
        return dict(_state)
