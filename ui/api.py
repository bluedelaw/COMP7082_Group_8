# ui/api.py
from __future__ import annotations

import os
import requests
import gradio as gr

def server_url() -> str:
    """
    Resolve the FastAPI base URL used by the Gradio front-end.
    Defaults to local server to match server.py.
    """
    return os.environ.get("JARVIN_SERVER_URL", "http://127.0.0.1:8000").rstrip("/")

# ---------------- HTTP helpers ----------------
def api_get_status(timeout: float = 2.0) -> dict:
    try:
        r = requests.get(f"{server_url()}/status", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"listening": False, "error": str(e)}

def api_get_live(timeout: float = 2.0) -> dict:
    try:
        r = requests.get(f"{server_url()}/live", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}

def api_post_start(timeout: float = 2.0) -> None:
    try:
        requests.post(f"{server_url()}/start", timeout=timeout)
    except Exception:
        pass

def api_post_stop(timeout: float = 2.0) -> None:
    try:
        requests.post(f"{server_url()}/stop", timeout=timeout)
    except Exception:
        pass

def api_post_shutdown(timeout: float = 2.0) -> None:
    try:
        requests.post(f"{server_url()}/shutdown", timeout=timeout)
    except Exception:
        pass

# Optional: endpoints not currently used by the UI, but handy
def api_post_transcribe(filepath: str, timeout: float = 60.0) -> dict:
    with open(filepath, "rb") as f:
        files = {"audio_file": (os.path.basename(filepath), f, "audio/wav")}
        r = requests.post(f"{server_url()}/transcribe", files=files, timeout=timeout)
    r.raise_for_status()
    return r.json()

def api_post_chat(user_text: str, context: str | None = None,
                  temperature: float | None = None, max_tokens: int | None = None,
                  system_instructions: str | None = None, timeout: float = 60.0) -> dict:
    payload = {
        "user_text": user_text,
        "context": context,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "system_instructions": system_instructions,
    }
    r = requests.post(f"{server_url()}/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()

# ---------------- Small UI utilities ----------------
def status_badge(listening: bool, recording: bool, processing: bool) -> str:
    if not listening:
        return '<span class="status-badge status-stopped">Stopped</span>'
    if recording:
        return '<span class="status-badge status-recording">Recording</span>'
    if processing:
        return ('<span class="status-badge" '
                'style="background:#78350f;color:#fde68a;">Processing</span>')
    return '<span class="status-badge status-listening">Listening</span>'

def status_str(status: dict | None, live: dict | None) -> str:
    listening = bool((status or {}).get("listening", False))
    live = live or {}
    recording = bool(live.get("recording", False)) if listening else False
    processing = bool(live.get("processing", False)) if listening else False
    return status_badge(listening, recording, processing)

def button_updates(listening: bool, *, disable_all: bool = False) -> tuple[gr.Update, gr.Update]:
    """
    Returns (start_btn_update, pause_btn_update):
      - Start enabled only when not listening
      - Pause enabled only when listening
      - If disable_all=True, both disabled
    """
    if disable_all:
        return (gr.update(interactive=False), gr.update(interactive=False))
    return (gr.update(interactive=not listening), gr.update(interactive=listening))
