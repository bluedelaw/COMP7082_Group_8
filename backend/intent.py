# backend/intent.py
from __future__ import annotations

import re

"""
Intent detection utilities kept separate from runtime code.

Exports:
- intent_shutdown(text: str) -> bool
- intent_confirm(text: str) -> bool
- CONFIRM_WINDOW_SEC: float
"""

# Deterministic voice shutdown detection
_SHUTDOWN_HOTWORDS = re.compile(
    r"\b("
    r"shut\s*down|shutdown|power\s*off|turn\s*off|stop\s+listening|stop\s+the\s+server|stop\s+server|"
    r"exit|quit|terminate|end\s+(?:session|process|server)|kill\s+(?:it|process|server)"
    r")\b",
    re.IGNORECASE,
)

# Negations that cancel detected intents
_NEGATIONS = re.compile(r"\b(don't|do\s+not|not\s+now|cancel|false\s+alarm)\b", re.IGNORECASE)

# Optional confirmation hotwords
_CONFIRM_HOTWORDS = re.compile(
    r"\b(confirm(?:ed)?\s+(?:shut\s*down|shutdown|exit|quit)|yes[, ]*(?:shut\s*down|exit)|go\s+ahead)\b",
    re.IGNORECASE,
)

# Window used by the caller when two-step confirmation is enabled
CONFIRM_WINDOW_SEC: float = 15.0


def intent_shutdown(text: str) -> bool:
    """Return True if text expresses a shutdown intent (unless negated)."""
    if _NEGATIONS.search(text):
        return False
    return bool(_SHUTDOWN_HOTWORDS.search(text))


def intent_confirm(text: str) -> bool:
    """Return True if text confirms a previously detected shutdown intent (unless negated)."""
    if _NEGATIONS.search(text):
        return False
    return bool(_CONFIRM_HOTWORDS.search(text))
