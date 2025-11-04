# ui/handlers.py
from __future__ import annotations

from typing import Any

import gradio as gr

from ui.actions import (
    save_user_profile,
    clear_conversation_history,
    update_history_display,
    get_save_confirmation,
)
from ui.api import (
    api_post_start,
    api_post_stop,
    api_post_shutdown,
    api_get_status,
    api_get_live,
    status_str,
    button_updates,
)
from ui.poller import Poller


# ---------- Profile tab bindings ----------

def bind_profile_actions(components: dict) -> None:
    # Save profile
    components["save_btn"].click(
        fn=save_user_profile,
        inputs=[
            components["name"],
            components["goal"],
            components["mood"],
            components["communication_style"],
            components["response_length"],
        ],
        outputs=[components["user_context"]],
    ).then(fn=get_save_confirmation, outputs=[components["status"]])

    # Keep history display in sync
    components["conversation_memory"].change(
        fn=update_history_display,
        inputs=[components["conversation_memory"]],
        outputs=[components["history_display"]],
    )


# ---------- Live tab helpers ----------

def _clear_all_conversation():
    history = clear_conversation_history()
    return "", "", history


def _start_listener():
    api_post_start()
    s = api_get_status()
    l = api_get_live()
    banner = status_str(s, l) or "&nbsp;"
    start_u, pause_u = button_updates(bool(s.get("listening", False)))
    return banner, start_u, pause_u


def _stop_listener():
    api_post_stop()
    banner = '<span class="status-badge status-stopped">Stopped</span>'
    start_u, pause_u = button_updates(False)
    return banner, start_u, pause_u


def _shutdown_server():
    api_post_shutdown()
    start_u, pause_u = button_updates(False, disable_all=True)
    return ('<span class="status-badge status-stopped">Shutting down…</span>', start_u, pause_u)


# ---------- Live tab bindings ----------

def bind_live_actions(components: dict) -> None:
    # Clear conversation + reflect into textboxes
    components["clear_btn"].click(
        fn=_clear_all_conversation,
        outputs=[
            components["current_transcription"],
            components["current_reply"],
            components["conversation_memory"],
        ],
    ).then(
        fn=lambda ct, cr: (ct, cr),
        inputs=[components["current_transcription"], components["current_reply"]],
        outputs=[components["transcription"], components["ai_reply"]],
    )

    # Start/Pause/Shutdown controls
    components["start_btn"].click(
        fn=_start_listener,
        outputs=[components["status_banner"], components["start_btn"], components["stop_btn"]],
    )
    components["stop_btn"].click(
        fn=_stop_listener,
        outputs=[components["status_banner"], components["start_btn"], components["stop_btn"]],
    )
    components["shutdown_btn"].click(
        fn=_shutdown_server,
        outputs=[components["status_banner"], components["start_btn"], components["stop_btn"]],
    )


# ---------- Polling (timer) ----------

def bind_polling(components: dict) -> None:
    """Attach Poller() and Timer()."""
    poller = Poller()
    timer = gr.Timer(value=0.5, active=True)
    timer.tick(
        fn=poller.tick,
        inputs=[components["conversation_memory"]],
        outputs=[
            components["status_banner"],
            components["transcription"],
            components["ai_reply"],
            components["metrics"],
            components["conversation_memory"],
            components["start_btn"],
            components["stop_btn"],
        ],
    )
