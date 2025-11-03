# ui/actions.py
from __future__ import annotations

from memory.conversation import (
    get_conversation_history, set_conversation_history,
    get_user_profile, set_user_profile, clear_conversation
)

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

def clear_conversation_history():
    clear_conversation()
    return get_conversation_history()

def update_history_display(history):
    if not history:
        return "No conversation history yet."
    out = []
    for i, (role, message) in enumerate(history, 1):
        speaker = "You" if role == "user" else "Jarvin"
        out.append(f"{i}. {speaker}: {message}\n")
    return "\n".join(out)

def get_save_confirmation():
    profile = get_user_profile()
    return f"✅ Profile saved! Jarvin will remember: {profile.get('name','Unknown')} - {profile.get('goal','No goal set')}"
