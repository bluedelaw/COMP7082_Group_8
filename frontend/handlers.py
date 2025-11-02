# frontend/handlers.py
import time
import hashlib
import os
import requests

from memory.conversation import (
    get_conversation_history, set_conversation_history,
    get_user_profile, set_user_profile, clear_conversation
)

# System prompt (client-provided; server accepts overrides)
JARVIN_SYSTEM_PROMPT = (
    "You are Jarvin, a friendly and helpful AI assistant. "
    "Your tone should be warm, encouraging, and positive. "
    "Keep responses concise but helpful."
)

last_processed_audio = None
is_processing = False
last_processing_time = 0.0
last_successful_response: tuple[str, str] | None = None

def _server_url() -> str:
    # Default aligns with server.py
    return os.environ.get("JARVIN_SERVER_URL", "http://127.0.0.1:8000").rstrip("/")

def _api_transcribe(audio_path: str) -> str:
    url = f"{_server_url()}/transcribe"
    with open(audio_path, "rb") as f:
        files = {"audio_file": (os.path.basename(audio_path), f, "audio/wav")}
        r = requests.post(url, files=files, timeout=60)
    r.raise_for_status()
    data = r.json()
    if "transcribed_text" in data:
        return data["transcribed_text"]
    raise RuntimeError(f"Unexpected transcribe response: {data}")

def _api_chat(user_text: str, context: str | None, temperature: float | None, max_tokens: int | None, system_prompt: str | None) -> str:
    url = f"{_server_url()}/chat"
    payload = {
        "user_text": user_text,
        "context": context,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "system_instructions": system_prompt,
    }
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    if "reply" in data:
        return data["reply"]
    if "error" in data:
        raise RuntimeError(data["error"])
    raise RuntimeError(f"Unexpected chat response: {data}")

def get_audio_hash(audio_path: str) -> str | None:
    if not audio_path or not os.path.exists(audio_path):
        return None
    try:
        stat = os.stat(audio_path)
        return hashlib.md5(f"{audio_path}_{stat.st_size}_{stat.st_mtime}".encode()).hexdigest()[:16]
    except Exception:
        return hashlib.md5(f"{audio_path}_{time.time()}".encode()).hexdigest()[:16]

def process_audio(audio_path: str, user_context: dict, use_conversation_memory: bool, response_style: str):
    global last_processed_audio, is_processing, last_processing_time, last_successful_response

    history = get_conversation_history()

    if not audio_path or not os.path.exists(audio_path):
        return "No audio input detected.", "No reply generated.", history

    cur_hash = get_audio_hash(audio_path)

    if is_processing:
        if history:
            # Return last entries to keep UI responsive
            last_user = next((m for (role,m) in reversed(history) if role=="user"), "Processing...")
            last_ai   = next((m for (role,m) in reversed(history) if role=="assistant"), "Please wait...")
            return last_user, last_ai, history
        return "Processing...", "Please wait...", history

    if cur_hash == last_processed_audio and last_successful_response:
        t, r = last_successful_response
        return t, r, history

    now = time.time()
    if (now - last_processing_time) < 2.0 and last_successful_response:
        t, r = last_successful_response
        return t, r, history

    is_processing = True
    last_processed_audio = cur_hash
    last_processing_time = now

    try:
        # 1) Transcribe via API
        text = (_api_transcribe(audio_path) or "").strip()
        if not text:
            return "(empty transcription)", "No reply generated.", history

        # 2) Build context to send to server
        profile_ctx = ""
        if user_context:
            profile_ctx = (
                f"User Name: {user_context.get('name','Unknown')}\n"
                f"Goal: {user_context.get('goal','None')}\n"
                f"Mood: {user_context.get('mood','Neutral')}\n"
            )

        style_prompt = ""
        if response_style == "concise":
            style_prompt = "Keep the response brief and to the point."
        elif response_style == "detailed":
            style_prompt = "Provide more detail and explanation."
        elif response_style == "encouraging":
            style_prompt = "Be encouraging and motivational."

        convo_ctx = ""
        if use_conversation_memory and history:
            recent = history[-6:]  # last ~3 exchanges
            convo_ctx = "Recent conversation:\n" + "\n".join(f"{role}: {msg}" for role, msg in recent) + "\n"

        context = "\n\n".join(part for part in [style_prompt, profile_ctx, convo_ctx] if part).strip() or None

        # 3) Chat via API
        reply = _api_chat(
            user_text=f"Current user message: {text}\n\nPlease respond helpfully:",
            context=context,
            temperature=None,
            max_tokens=None,
            system_prompt=JARVIN_SYSTEM_PROMPT,
        )

        # 4) Update memory
        history.append(("user", text))
        history.append(("assistant", reply))
        set_conversation_history(history)
        last_successful_response = (text, reply)
        return text, reply, history

    except Exception as e:
        return f"Error: {e}", "Sorry, there was an error processing your request.", history
    finally:
        is_processing = False

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
    global last_successful_response, last_processed_audio
    clear_conversation()
    last_successful_response = None
    last_processed_audio = None
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
    from memory.conversation import get_user_profile
    profile = get_user_profile()
    return f"✅ Profile saved! Jarvin will remember: {profile.get('name','Unknown')} - {profile.get('goal','No goal set')}"
