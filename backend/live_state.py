# backend/live_state.py
from __future__ import annotations
import threading
from typing import Any, Dict, Optional
import time

_lock = threading.Lock()
_state: Dict[str, Any] = {
    "ts": None,             # monotonic seconds
    "utter_ms": None,       # last utterance duration (ms)
    "transcript": None,     # last recognized text
    "reply": None,          # last LLM reply
    "cycle_ms": None,       # last end-to-end latency
    "wav_path": None,       # temp path of last wav (optional)
    # NEW: UI activity flags
    "recording": False,     # true while VAD is inside an utterance
    "llm_busy": False,      # true while generating LLM reply for last transcript
}

def set_activity(*, recording: Optional[bool] = None, llm_busy: Optional[bool] = None) -> None:
    """Update live activity flags without touching transcript/reply fields."""
    with _lock:
        if recording is not None:
            _state["recording"] = bool(recording)
            _state["ts"] = time.monotonic()
        if llm_busy is not None:
            _state["llm_busy"] = bool(llm_busy)
            _state["ts"] = time.monotonic()

def set_snapshot(*, transcript: Optional[str], reply: Optional[str],
                 cycle_ms: Optional[int], utter_ms: Optional[int],
                 wav_path: Optional[str], llm_busy: Optional[bool] = None) -> None:
    with _lock:
        _state.update({
            "ts": time.monotonic(),
            "transcript": transcript,
            "reply": reply,
            "cycle_ms": cycle_ms,
            "utter_ms": utter_ms,
            "wav_path": wav_path,
        })
        if llm_busy is not None:
            _state["llm_busy"] = bool(llm_busy)

def get_snapshot() -> Dict[str, Any]:
    with _lock:
        return dict(_state)  # shallow copy
