# ui/handlers.py
from __future__ import annotations

import logging
import time
from typing import List, Tuple
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
    api_get_audio_devices,
    api_post_audio_select,
)
from backend.listener.live_state import get_snapshot

log = logging.getLogger("jarvin.ui.audio")


def _short(s: str | None, n: int = 80) -> str:
    if not s:
        return ""
    return s if len(s) <= n else (s[: n - 1] + "…")


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

    # Keep history display in sync if conversation_memory changes outside the poller (e.g., Clear)
    components["conversation_memory"].change(
        fn=update_history_display,
        inputs=[components["conversation_memory"]],  # type: ignore[arg-type]
        outputs=[components["history_display"]],
    )

    # ---- Mic device UI helpers ----
    def _present_from_data(data: dict):
        devices = data.get("devices", [])
        sel_idx = data.get("selected_index")
        sel_name = data.get("selected_name")
        choices = [f"[{d['index']}] {d['name']}" for d in devices]
        selected = f"[{sel_idx}] {sel_name}" if sel_idx is not None and sel_name else None
        label = (f"**Current input device:** `{sel_idx}` — **{sel_name}**"
                 if sel_idx is not None and sel_name else "_No input device available_")
        return choices, selected, label

    def _value_to_index(value: str | None) -> int | None:
        if not value:
            return None
        try:
            return int(value.split("]", 1)[0].strip("[ "))
        except Exception:
            return None

    def _load_devices_ui() -> Tuple[List[str], str | None, str]:
        t0 = time.perf_counter()
        data = api_get_audio_devices()
        choices, selected, label = _present_from_data(data)
        dt = (time.perf_counter() - t0) * 1000
        log.debug("UI load devices -> selected=%s | choices=%d | %.1f ms", _short(selected), len(choices), dt)
        return choices, selected, label

    def _refresh_devices():
        log.debug("UI manual refresh devices clicked")
        choices, selected, label = _load_devices_ui()
        return gr.update(choices=choices, value=selected), label

    def _apply_device(value: str | None):
        log.debug("UI device dropdown changed -> raw_value=%r", value)
        idx = _value_to_index(value)
        if idx is None:
            log.debug("UI device change ignored: could not parse index from %r", value)
            return gr.update(), "⚠️ Invalid selection."

        before = api_get_audio_devices()
        cur_idx = before.get("selected_index")
        cur_name = before.get("selected_name")
        if cur_idx is not None and idx == cur_idx:
            choices, selected, label = _present_from_data(before)
            log.debug("UI device change is no-op (already selected index=%s name=%s)", str(cur_idx), _short(cur_name))
            return gr.update(choices=choices, value=selected), f"✅ Already using {label}"

        log.info("UI applying new device index=%d (prev=%s:%s) -> POST /audio/select", idx, str(cur_idx), _short(cur_name))
        t0 = time.perf_counter()
        res = api_post_audio_select(idx, restart=True)
        if not res.get("ok", False):
            dt = (time.perf_counter() - t0) * 1000
            err = res.get("error", "unknown error")
            log.error("UI apply device failed in %.1f ms -> %s", dt, err)
            return gr.update(), f"❌ Failed to select device: {err}"

        after = api_get_audio_devices()
        choices, selected, label = _present_from_data(after)
        dt = (time.perf_counter() - t0) * 1000
        log.info("UI device applied in %.1f ms -> now selected index=%s name=%s",
                 dt, str(after.get("selected_index")), _short(after.get("selected_name")))
        return gr.update(choices=choices, value=selected), f"✅ Switched to {label}"

    components["device_refresh_btn"].click(
        fn=_refresh_devices,
        outputs=[components["device_dropdown"], components["device_current"]],
        queue=False,
        show_progress=False,
    )
    components["device_dropdown"].change(
        fn=_apply_device,
        inputs=[components["device_dropdown"]],
        outputs=[components["device_dropdown"], components["device_current"]],
        show_progress=False,
    )

    components["_init_devices_fn"] = _refresh_devices


# ---------- Live tab bindings (no generator streams; poller owns updates) ----------

def bind_live_actions(components: dict) -> None:
    # Clear conversation -> wipe state + textboxes
    def _clear_all_conversation():
        history = clear_conversation_history()
        return "", "", history

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
    ).then(
        fn=update_history_display,
        inputs=[components["conversation_memory"]],
        outputs=[components["history_display"]],
    )

    # Start / Stop / Shutdown simply flip server state; poller reflects UI promptly
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

    components["start_btn"].click(
        fn=_start_listener,
        outputs=[components["status_banner"], components["start_btn"], components["stop_btn"]],
        concurrency_limit=4,
    )
    components["stop_btn"].click(
        fn=_stop_listener,
        outputs=[components["status_banner"], components["start_btn"], components["stop_btn"]],
        concurrency_limit=4,
    )
    components["shutdown_btn"].click(
        fn=_shutdown_server,
        outputs=[components["status_banner"], components["start_btn"], components["stop_btn"]],
        concurrency_limit=2,
    )
