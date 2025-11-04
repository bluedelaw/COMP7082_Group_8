# ui/handlers.py
from __future__ import annotations

from typing import Generator
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
    status_str,
    button_updates,
)
from backend.listener.live_state import get_snapshot, wait_next


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
        inputs=[components["conversation_memory"]],  # type: ignore[arg-type]
        outputs=[components["history_display"]],
    )


# ---------- Live tab helpers ----------

def _clear_all_conversation():
    history = clear_conversation_history()
    return "", "", history

def _start_listener():
    api_post_start()
    s = api_get_status()
    banner = status_str(s, get_snapshot()) or "&nbsp;"
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


# ---------- Status-only polling (keeps banner/buttons fresh) ----------

def _status_tick():
    """
    Polled via gr.Timer: only updates the banner + start/pause interactivity.
    Transcript/reply/metrics/history are driven by the stream below.
    """
    s = api_get_status()
    l = get_snapshot()  # local state for recording/processing
    banner = status_str(s, l) or "&nbsp;"
    start_u, pause_u = button_updates(bool(s.get("listening", False)))
    return banner, start_u, pause_u


# ---------- Stream (no timer) for transcript/reply/metrics/history ----------

def _format_metrics(l: dict) -> str:
    utt_ms = l.get("utter_ms")
    cyc_ms = l.get("cycle_ms")
    parts = []
    if isinstance(utt_ms, int):
        parts.append(f"🎙️ utterance: {utt_ms} ms")
    if isinstance(cyc_ms, int):
        parts.append(f"⏱️ cycle: {cyc_ms} ms")
    return " | ".join(parts) if parts else "&nbsp;"

def _live_stream(conversation_memory: list[tuple[str, str]] | None) -> Generator[
    tuple[str, str, str, list[tuple[str, str]]], None, None
]:
    """
    Streaming generator: emits once immediately (to keep the pipe open), then
    blocks in wait_next() and only yields when there’s a *new utterance*.
    """
    snap = get_snapshot()
    last_seq = snap.get("seq") if isinstance(snap.get("seq"), int) else None
    hist = (conversation_memory or []).copy()

    # Immediate first yield so Gradio holds the connection
    t0 = (snap.get("transcript") or "").strip()
    r0 = (snap.get("reply") or "").strip()
    m0 = _format_metrics(snap)
    yield (t0, r0, m0, hist)

    # If an utterance already exists, reflect it once
    if last_seq is not None and (t0 or r0):
        if t0:
            hist.append(("user", t0))
        if r0:
            hist.append(("assistant", r0))

    # Main loop: wait for the *next* utterance (seq bump)
    while True:
        next_snap = wait_next(since=last_seq, timeout=None)
        next_seq = next_snap.get("seq") if isinstance(next_snap.get("seq"), int) else last_seq

        if next_seq != last_seq:
            last_seq = next_seq
            t_now = (next_snap.get("transcript") or "").strip()
            r_now = (next_snap.get("reply") or "").strip()
            if t_now:
                hist.append(("user", t_now))
            if r_now:
                hist.append(("assistant", r_now))
            yield (t_now, r_now, _format_metrics(next_snap), hist)
        # status flips wake waiters, but without seq change the status poller handles UI.


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
    start_evt = components["start_btn"].click(
        fn=_start_listener,
        outputs=[components["status_banner"], components["start_btn"], components["stop_btn"]],
        concurrency_limit=4,
    )

    # Attach the long-lived stream *after* starting the listener
    stream_evt = start_evt.then(
        fn=_live_stream,
        inputs=[components["conversation_memory"]],
        outputs=[
            components["transcription"],
            components["ai_reply"],
            components["metrics"],
            components["conversation_memory"],
        ],
        show_progress=False,
        concurrency_limit=1,  # exactly one stream per session
    )

    # Status-only polling (timer) — lightweight and independent of the stream
    timer = gr.Timer(value=1.0, active=True)
    timer.tick(
        fn=_status_tick,
        outputs=[components["status_banner"], components["start_btn"], components["stop_btn"]],
        concurrency_limit=16,
    )

    # Stop / Shutdown: cancel the active stream event
    components["stop_btn"].click(
        fn=_stop_listener,
        outputs=[components["status_banner"], components["start_btn"], components["stop_btn"]],
        cancels=[stream_evt],
        concurrency_limit=4,
    )
    components["shutdown_btn"].click(
        fn=_shutdown_server,
        outputs=[components["status_banner"], components["start_btn"], components["stop_btn"]],
        cancels=[stream_evt],
        concurrency_limit=2,
    )