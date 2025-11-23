# ui/poller.py
from __future__ import annotations

from typing import Any
import gradio as gr

from ui.api import (
    api_get_status, api_get_live, server_url,
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

        # metrics edge detection (processing True -> False)
        self._last_processing: bool | None = None
        self._last_metrics_key: tuple[int | None, int | None] | None = None

        # audio
        self._last_tts_url: str | None = None

        # button state
        self._btn_state: dict[str, tuple[Any, Any, Any] | None] = {
            "start": None,
            "pause": None,
        }

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
        Returns tuple matching outputs in app.py:
          (status_banner, metrics, conversation_memory, start_btn, stop_btn, tts_audio)
        """
        try:
            banner_out, start_u, pause_u, s, l = self._status_updates()

            # Current values from /live
            t_now = (l.get("transcript") or "").strip()
            r_now = (l.get("reply") or "").strip()
            tts_rel = (l.get("tts_url") or "").strip()
            tts_abs = (server_url() + tts_rel) if tts_rel else ""

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

            # Conversation history append-on-change:
            #   - Use current transcript/reply
            #   - Avoid duplicating the last user/assistant pair.
            hist_out = gr.update()
            if t_now:
                hist = list(conversation_memory or [])
                tail = hist[-2:]
                duplicate = False
                if len(tail) == 2:
                    last_user_role, last_user_msg = tail[0]
                    last_ass_role, last_ass_msg = tail[1]
                    if (
                        last_user_role == "user"
                        and last_user_msg == t_now
                        and last_ass_role == "assistant"
                        and (not r_now or last_ass_msg == r_now)
                    ):
                        duplicate = True

                if not duplicate:
                    hist.append(("user", t_now))
                    if r_now:
                        hist.append(("assistant", r_now))
                    hist_out = hist

            # TTS audio update: only when URL changes
            audio_out = gr.update()
            if tts_abs and tts_abs != self._last_tts_url:
                audio_out = tts_abs
                self._last_tts_url = tts_abs

            return (
                banner_out,   # status_banner
                metrics_out,  # metrics
                hist_out,     # conversation_memory
                start_u,      # start button
                pause_u,      # stop button
                audio_out,    # tts audio
            )

        except Exception:
            # Never let the timer die — return "no changes" for all outputs.
            return (
                gr.update(),  # status_banner
                gr.update(),  # metrics
                gr.update(),  # conversation_memory
                gr.update(),  # start button
                gr.update(),  # stop button
                gr.update(),  # tts audio
            )
