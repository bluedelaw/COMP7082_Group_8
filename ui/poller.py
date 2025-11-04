# ui/poller.py
from __future__ import annotations

from typing import Any, Tuple
import gradio as gr

from ui.api import (
    api_get_status, api_get_live,
    status_str, button_updates,
)


class Poller:
    """
    Encapsulates the UI polling state so the UI code in app.py stays small.
    Produces minimal updates (anti-flicker) by diffing previous values.
    """

    def __init__(self) -> None:
        # status/banner
        self._last_banner: str | None = None

        # transcript/reply
        self._last_transcript: str | None = None
        self._last_reply: str | None = None

        # metrics edge detection (processing True -> False)
        self._last_processing: bool | None = None
        self._last_metrics_key: tuple[int | None, int | None] | None = None

        # conversation history change detection
        self._last_hist_len: int = 0

        # button state
        self._btn_state: dict[str, tuple[Any, Any, Any] | None] = {"start": None, "pause": None}

    @staticmethod
    def _norm_btn_state(u: dict) -> tuple[Any, Any, Any]:
        # gr.update(...) returns a dict-like; normalize to a comparable tuple
        return (u.get("interactive", None), u.get("visible", None), u.get("value", None))

    def _status_updates(self):
        """
        Fetch /status and /live and compute banner + button updates.
        Returns: (banner_out, start_btn_update, stop_btn_update, status_json, live_json)
        """
        s = api_get_status()
        l = api_get_live()

        # Banner
        banner_now = status_str(s, l) or "&nbsp;"
        if banner_now != self._last_banner:
            banner_out = banner_now
            self._last_banner = banner_now
        else:
            banner_out = gr.update()

        # Buttons
        listening = bool(s.get("listening", False))
        start_u_raw, pause_u_raw = button_updates(listening)

        start_tuple = self._norm_btn_state(start_u_raw)
        pause_tuple = self._norm_btn_state(pause_u_raw)

        if start_tuple != self._btn_state["start"]:
            start_u = start_u_raw
            self._btn_state["start"] = start_tuple
        else:
            start_u = gr.update()

        if pause_tuple != self._btn_state["pause"]:
            pause_u = pause_u_raw
            self._btn_state["pause"] = pause_tuple
        else:
            pause_u = gr.update()

        return banner_out, start_u, pause_u, s, l

    def tick(self, conversation_memory: list[tuple[str, str]] | None):
        """
        Gradio Timer callback.
        Returns tuple matching outputs in app.py.
        """
        banner_out, start_u, pause_u, s, l = self._status_updates()

        # Current values
        t_now = (l.get("transcript") or "").strip()
        r_now = (l.get("reply") or "").strip()

        # Determine if either changed BEFORE mutating caches (fixes history not updating)
        transcript_changed = t_now != self._last_transcript
        reply_changed = r_now != self._last_reply
        pair_changed = transcript_changed or reply_changed

        # Metrics: edge detect processing True -> False
        utt_ms = l.get("utter_ms")
        cyc_ms = l.get("cycle_ms")
        processing_now = bool(l.get("processing", False))

        metrics_out = gr.update()
        if self._last_processing is True and processing_now is False:
            key = (
                int(utt_ms) if utt_ms is not None else None,
                int(cyc_ms) if cyc_ms is not None else None,
            )
            if key != self._last_metrics_key:
                parts = []
                if utt_ms is not None:
                    parts.append(f"🎙️ utterance: {int(utt_ms)} ms")
                if cyc_ms is not None:
                    parts.append(f"⏱️ cycle: {int(cyc_ms)} ms")
                metrics_out = " | ".join(parts) if parts else "&nbsp;"
                self._last_metrics_key = key
        self._last_processing = processing_now

        # Conversation history append-on-change (uses old caches intentionally)
        hist = (conversation_memory or []).copy()
        if t_now and pair_changed:
            hist.append(("user", t_now))
            if r_now:
                hist.append(("assistant", r_now))
            hist_out = hist
        else:
            hist_out = gr.update()

        # Now update caches and textbox outputs
        if transcript_changed:
            t_out = t_now
            self._last_transcript = t_now
        else:
            t_out = gr.update()

        if reply_changed:
            r_out = r_now
            self._last_reply = r_now
        else:
            r_out = gr.update()

        return (
            banner_out,  # status_banner
            t_out,       # transcription
            r_out,       # ai_reply
            metrics_out, # metrics
            hist_out,    # conversation_memory
            start_u,     # start button
            pause_u,     # stop button
        )
