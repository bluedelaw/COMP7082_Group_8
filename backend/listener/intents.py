# backend/listener/intents.py
from __future__ import annotations
import re

_SHUTDOWN_HOTWORDS = re.compile(
    r"\b("
    r"shut\s*down|shutdown|power\s*off|turn\s*off|stop\s+listening|stop\s+the\s+server|stop\s+server|"
    r"exit|quit|terminate|end\s+(?:session|process|server)|kill\s+(?:it|process|server)"
    r")\b",
    re.IGNORECASE,
)
_NEGATIONS = re.compile(r"\b(don't|do\s+not|not\s+now|cancel|false\s+alarm)\b", re.IGNORECASE)
_CONFIRM_HOTWORDS = re.compile(
    r"\b(confirm(?:ed)?\s+(?:shut\s*down|shutdown|exit|quit)|yes[, ]*(?:shut\s*down|exit)|go\s+ahead)\b",
    re.IGNORECASE,
)
CONFIRM_WINDOW_SEC: float = 15.0

def intent_shutdown(text: str) -> bool:
    if _NEGATIONS.search(text):
        return False
    return bool(_SHUTDOWN_HOTWORDS.search(text))

def intent_confirm(text: str) -> bool:
    if _NEGATIONS.search(text):
        return False
    return bool(_CONFIRM_HOTWORDS.search(text))
