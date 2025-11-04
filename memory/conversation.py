# memory/conversation.py
from __future__ import annotations

import threading
from typing import Any, Dict, List, Tuple

# Simple thread-safe in-process memory for UI-only state.
# (Gradio can run multiple workers; guard with a lock.)
_lock = threading.Lock()
_conversation_history: List[Tuple[str, str]] = []
_user_profile: Dict[str, Any] = {}
_last_processed_audio: Any = None  # path or opaque handle


def get_conversation_history() -> List[Tuple[str, str]]:
    with _lock:
        # return a shallow copy to avoid external mutation
        return list(_conversation_history)


def set_conversation_history(history: List[Tuple[str, str]]) -> None:
    with _lock:
        _conversation_history.clear()
        _conversation_history.extend(history)


def append_turn(role: str, message: str) -> None:
    with _lock:
        _conversation_history.append((role, message))


def get_user_profile() -> Dict[str, Any]:
    with _lock:
        return dict(_user_profile)


def set_user_profile(profile: Dict[str, Any]) -> None:
    with _lock:
        _user_profile.update(profile)


def clear_conversation() -> None:
    global _last_processed_audio
    with _lock:
        _conversation_history.clear()
        _last_processed_audio = None
