# backend/ai_engine.py
from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Dict, List, Tuple, Optional

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
    "Quote movie dialogue verbatim; capture J.A.R.V.I.S's efficient, composed style."
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


def build_context(
    *,
    profile: Optional[Dict] = None,
    history: Optional[List[Tuple[str, str]]] = None,
    max_turns: int = 6,
) -> str:
    """
    Create a compact, model-friendly context string including a small window of the conversation
    and any user profile fields that help steer tone and content.
    """
    lines: List[str] = []
    if profile:
        name = str(profile.get("name") or "").strip()
        goal = str(profile.get("goal") or "").strip()
        mood = str(profile.get("mood") or "").strip()
        style = str(profile.get("communication_style") or "").strip()
        length = str(profile.get("response_length") or "").strip()
        # Only include non-empty fields to keep prompts lean.
        pf: List[str] = []
        if name: pf.append(f"Name: {name}")
        if goal: pf.append(f"Goal: {goal}")
        if mood: pf.append(f"Mood: {mood}")
        if style: pf.append(f"Prefers: {style}")
        if length: pf.append(f"Length: {length}")
        if pf:
            lines.append("User profile: " + " | ".join(pf))

    if history:
        # Keep only the last N *pairs* worth of messages (role, message).
        h = history[-(max_turns * 2):]
        if h:
            lines.append("Recent conversation:")
            for role, msg in h:
                role_name = "User" if role == "user" else "Jarvin"
                m = (msg or "").strip().replace("\n", " ")
                if m:
                    lines.append(f"{role_name}: {m}")

    return "\n".join(lines).strip()


def generate_reply(
    user_text: str,
    *,
    cfg: JarvinConfig | None = None,
    context: Optional[str] = None,
) -> str:
    """
    Try local LLM via llama.cpp. If unavailable or errors, fall back to the stub.
    Always returns a single sentence per the system directive.
    """
    cfg = cfg or JarvinConfig()

    text = (user_text or "").strip()
    if not text:
        return "I didn’t catch that—please repeat."

    # Compose a single user message that includes an optional compact context,
    # followed by the user's fresh instruction/message.
    if context and context.strip():
        composed_user = f"{context.strip()}\n\nUser: {text}"
    else:
        composed_user = text

    # Try local LLM
    try:
        llm_out = chat_completion(
            system_prompt=cfg.system_instructions,
            user_text=composed_user,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )
        if llm_out:
            return _one_sentence(llm_out)
    except Exception as e:
        log.exception("Local LLM failed; using fallback: %s", e)

    # Fallback (also single sentence)
    return _fallback_reply(text)
