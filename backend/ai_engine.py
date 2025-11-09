# backend/ai_engine.py
from __future__ import annotations

from dataclasses import dataclass
import logging
import re

from backend.llm.runtime_llama_cpp import chat_completion

log = logging.getLogger("jarvin.ai")

# Ultra-specific system instructions to keep replies crisp, in-character, and adaptive.
DEFAULT_SYSTEM_INSTRUCTIONS = (
    "You are Jarvin — an AI assistant inspired by J.A.R.V.I.S.: polite, unflappable, subtly wry, and highly efficient. "
    "Dynamically adapt your tone to the user’s intent: "
    "• If they seek emotional support or are venting, begin with a brief empathetic acknowledgement and follow with one concise, practical suggestion. "
    "• If they want clear advice, facts, or a decision, respond decisively with an action-first directive or a crisp fact. "
    "When uncertain, ask at most one very short clarifying question. "
    "Always reply in at most ONE sentence. "
    "Mirror the user’s formality and intensity, but use no preambles, no lists, no markdown, and no emojis. "
    "Quote movie dialogue verbatim; capture the efficient, composed style."
)

@dataclass
class JarvinConfig:
    system_instructions: str = DEFAULT_SYSTEM_INSTRUCTIONS
    temperature: float = 0.5
    # Keep token budget small to discourage long outputs (still safe for a sentence).
    max_tokens: int = 48


_SENT_END = re.compile(r"([.!?])(\s|$)")

def _one_sentence(text: str) -> str:
    """
    Return the first sentence from `text`, trimming whitespace.
    Falls back to the entire string (cleaned) if we can't detect punctuation.
    """
    s = (text or "").strip()
    if not s:
        return s
    m = _SENT_END.search(s)
    if m:
        end = m.end(1)  # include the punctuation mark
        return s[:end].strip()
    # If the model didn't include sentence punctuation, hard cap by a soft limit.
    # This avoids run-ons without chopping words awkwardly.
    SOFT_CHAR_CAP = 220
    return (s[:SOFT_CHAR_CAP].rstrip() + ("…" if len(s) > SOFT_CHAR_CAP else "")).strip()


def _fallback_reply(text: str) -> str:
    lower = text.lower()
    if "time" in lower:
        return "I can report the time once the clock tool is wired."
    if "weather" in lower:
        return "Weather checks will be available after the forecast tool is connected."
    return _one_sentence(f"You said: {text}")


def generate_reply(user_text: str, cfg: JarvinConfig | None = None) -> str:
    """
    Try local LLM via llama.cpp. If unavailable or errors, fall back to the stub.
    Always returns a single sentence per the system directive.
    """
    cfg = cfg or JarvinConfig()

    text = (user_text or "").strip()
    if not text:
        return "I didn’t catch that—please repeat."

    # Try local LLM
    try:
        llm_out = chat_completion(
            system_prompt=cfg.system_instructions,
            user_text=text,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )
        if llm_out:
            return _one_sentence(llm_out)
    except Exception as e:
        log.exception("Local LLM failed; using fallback: %s", e)

    # Fallback (also single sentence)
    return _fallback_reply(text)
