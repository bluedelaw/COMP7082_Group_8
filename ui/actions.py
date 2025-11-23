# ui/actions.py
from __future__ import annotations
from typing import Tuple, List, Dict
import html

from memory.conversation import (
    # Profile + history (scoped to ACTIVE conversation)
    get_conversation_history, set_conversation_history,
    get_user_profile, set_user_profile, clear_conversation,
    # NEW: multi-conversation controls
    list_conversations, new_conversation, rename_conversation, delete_conversation,
    get_active_conversation_id, set_active_conversation,
)

# -------- Profile --------

def save_user_profile(name, goal, mood, communication_style, response_length):
    profile = {
        "name": name,
        "goal": goal,
        "mood": mood,
        "communication_style": communication_style,
        "response_length": response_length,
    }
    set_user_profile(profile)
    return profile

def load_user_profile_fields():
    """
    Returns values (name, goal, mood, communication_style, response_length, status_markdown)
    to populate the Profile tab inputs on app load.
    """
    p = get_user_profile() or {}
    name = p.get("name") or ""
    goal = p.get("goal") or ""
    mood = p.get("mood") or "Focused"
    style = p.get("communication_style") or "Friendly"
    length = p.get("response_length") or "Balanced"

    status = ""
    if any([name, goal]):
        status = f"📦 Loaded saved profile for **{name or 'User'}**."

    return name, goal, mood, style, length, status


# -------- Conversation history (active) --------

def clear_conversation_history():
    clear_conversation()
    return get_conversation_history()

def update_history_display(history):
    """
    Render the active conversation as a ChatGPT-style log:

      - user messages right-aligned
      - assistant messages left-aligned

    Uses .chatline.user / .chatline.assistant + .bubble classes
    styled in ui/styles.py.
    """
    if not history:
        return (
            "<div class='chatline assistant'>"
            "<div class='bubble'>No conversation history yet.</div>"
            "</div>"
        )

    lines = []
    for role, message in history:
        if not message:
            continue
        role_cls = "user" if role == "user" else "assistant"
        text = html.escape(str(message))
        lines.append(
            f'<div class="chatline {role_cls}">'
            f'<div class="bubble">{text}</div>'
            f"</div>"
        )
    return "\n".join(lines)

def get_save_confirmation():
    profile = get_user_profile()
    return f"✅ Profile saved! Jarvin will remember: {profile.get('name','Unknown')} - {profile.get('goal','No goal set')}"


# -------- Multi-conversation helpers for UI --------

def _fmt_choice(item: Dict) -> str:
    # Render as "[id] title (N)"
    return f"[{item['id']}] {item['title']} ({item['messages']})"

def _parse_choice(val: str | None) -> int | None:
    if not val:
        return None
    try:
        return int(val.split("]", 1)[0].strip("[ "))
    except Exception:
        return None

def get_conversation_menu():
    """
    Returns (choices, selected_value, subtitle_markdown) for the Conversations UI.
    """
    items = list_conversations()
    active = get_active_conversation_id()
    choices = [_fmt_choice(it) for it in items]
    selected = None
    subtitle = ""
    for it in items:
        if it["id"] == active:
            selected = _fmt_choice(it)
            subtitle = f"**Active:** `{it['id']}` — **{it['title']}**"
            break
    if selected is None and choices:
        selected = choices[0]
        subtitle = "Select a conversation…"
    return choices, selected, subtitle

def activate_conversation(value: str | None):
    cid = _parse_choice(value)
    if cid is None:
        return get_conversation_menu(), get_conversation_history()
    set_active_conversation(cid)
    return get_conversation_menu(), get_conversation_history()

def create_conversation(title: str | None):
    cid = new_conversation((title or "").strip() or None, activate=True)
    return get_conversation_menu(), get_conversation_history()

def rename_active_conversation(new_title: str | None):
    active = get_active_conversation_id()
    rename_conversation(active, (new_title or "").strip() or "Conversation")
    return get_conversation_menu()

def delete_active_conversation():
    active = get_active_conversation_id()
    delete_conversation(active)
    # After deletion, an active convo is guaranteed; return its menu + history
    return get_conversation_menu(), get_conversation_history()
