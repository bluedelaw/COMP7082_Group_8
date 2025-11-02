# backend/live_state.py
from __future__ import annotations
import threading
from typing import Any, Dict, Optional
import time

_lock = threading.Lock()
_state: Dict[str, Any] = {
    "ts": None,             # monotonic seconds of last update
    "utter_ms": None,       # last utterance duration (ms)
    "transcript": None,     # last recognized text (None if none yet)
    "reply": None,          # last LLM reply (None if none yet)
    "cycle_ms": None,       # last end-to-end latency (ms)
    "wav_path": None,       # temp path of last wav (optional)
    "recording": False,     # true while VAD is inside an active-voice segment
    "processing": False,    # true while transcribing and/or generating reply
}

def set_snapshot(
    *, transcript: Optional[str], reply: Optional[str],
    cycle_ms: Optional[int], utter_ms: Optional[int],
    wav_path: Optional[str]
) -> None:
    """
    Atomic snapshot publish after each cycle. Leaves 'recording' and 'processing'
    flags unchanged (they're driven by set_status()).
    """
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
    """
    Lightweight status updates that can occur mid-utterance (e.g., toggle
    the live 'recording' indicator or 'processing' while ASR/LLM runs).
    """
    if recording is None and processing is None:
        return
    with _lock:
        if recording is not None:
            _state["recording"] = bool(recording)
        if processing is not None:
            _state["processing"] = bool(processing)
        _state["ts"] = time.monotonic()

def get_snapshot() -> Dict[str, Any]:
    """
    Return a shallow copy of the current state for /live.
    """
    with _lock:
        return dict(_state)
