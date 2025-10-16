# backend/ai_engine.py
from __future__ import annotations

from dataclasses import dataclass
import logging

from backend.llm_runtime import chat_completion

log = logging.getLogger("jarvin.ai")


DEFAULT_SYSTEM_INSTRUCTIONS = (
    "You are Jarvin, a concise helpful AI assistant."
)


@dataclass
class JarvinConfig:
    system_instructions: str = DEFAULT_SYSTEM_INSTRUCTIONS
    temperature: float = 0.7
    max_tokens: int = 256


def _fallback_reply(text: str) -> str:
    lower = text.lower()
    if "time" in lower:
        return "I can tell you the time later once tools are wired—right now I’m just a demo brain."
    if "weather" in lower:
        return "Weather lookups are coming soon. For now, hello from Jarvin!"
    return f"You said: {text}"


def generate_reply(user_text: str, cfg: JarvinConfig | None = None) -> str:
    """
    Try local LLM via llama.cpp. If unavailable or errors, fall back to the stub.
    """
    cfg = cfg or JarvinConfig()

    text = user_text.strip()
    if not text:
        return "I didn't catch that. Could you repeat?"

    # Try local LLM
    try:
        llm_out = chat_completion(
            system_prompt=cfg.system_instructions,
            user_text=text,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )
        if llm_out:
            return llm_out
    except Exception as e:
        log.exception("Local LLM failed; using fallback: %s", e)

    # Fallback
    return _fallback_reply(text)
