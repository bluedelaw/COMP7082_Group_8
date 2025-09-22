# backend/ai_engine.py
from __future__ import annotations

from dataclasses import dataclass


DEFAULT_SYSTEM_INSTRUCTIONS = (
    "You are Jarvin, a concise helpful AI assistant."
)


@dataclass
class JarvinConfig:
    system_instructions: str = DEFAULT_SYSTEM_INSTRUCTIONS


def generate_reply(user_text: str, cfg: JarvinConfig | None = None) -> str:
    """
    Placeholder: later, call your local LLM with system instructions + user_text.
    For now, do a tiny rule-based echo to prove wiring works.
    """
    cfg = cfg or JarvinConfig()

    text = user_text.strip()
    if not text:
        return "I didn't catch that. Could you repeat?"

    lower = text.lower()
    if "time" in lower:
        return "I can tell you the time later once tools are wired—right now I’m just a demo brain."
    if "weather" in lower:
        return "Weather lookups are coming soon. For now, hello from Jarvin!"
    return f"You said: {text}"
