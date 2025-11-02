# ui_app.py
import os
import requests
import gradio as gr
from frontend.components import CSS
from frontend.handlers import (
    save_user_profile, clear_conversation_history,
    update_history_display, get_save_confirmation
)

def create_app():
    with gr.Blocks(css=CSS) as demo:
        components = {}
        with gr.Row():
            gr.Markdown("<h1 style='margin:0'>Jarvin - Your AI Assistant</h1>")

        # Global state
        components['user_context'] = gr.State({})
        components['conversation_memory'] = gr.State([])
        components['current_transcription'] = gr.State("")
        components['current_reply'] = gr.State("")

        SERVER = os.environ.get("JARVIN_SERVER_URL", "http://127.0.0.1:8000").rstrip("/")

        # ---- Helpers --------------------------------------------------------
        def _status_badge(listening: bool, recording: bool, processing: bool) -> str:
            if not listening:
                return '<span class="status-badge status-stopped">Stopped</span>'
            if recording:
                return '<span class="status-badge status-recording">Recording</span>'
            if processing:
                return ('<span class="status-badge" '
                        'style="background:#78350f;color:#fde68a;">Processing</span>')
            return '<span class="status-badge status-listening">Listening</span>'

        def _status_str(status: dict | None, live: dict | None) -> str:
            listening = bool((status or {}).get("listening", False))
            live = live or {}
            recording = bool(live.get("recording", False)) if listening else False
            processing = bool(live.get("processing", False)) if listening else False
            return _status_badge(listening, recording, processing)

        def _get_status():
            try:
                r = requests.get(f"{SERVER}/status", timeout=2)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                return {"listening": False, "error": str(e)}

        def _get_live():
            try:
                r = requests.get(f"{SERVER}/live", timeout=2)
                r.raise_for_status()
                return r.json()
            except Exception:
                return {}

        def _button_updates(listening: bool, disabling_all: bool = False):
            """
            Start is active only when NOT listening.
            Pause is active only when listening.
            If disabling_all==True (e.g., after shutdown), both disabled.
            """
            if disabling_all:
                return (gr.update(interactive=False), gr.update(interactive=False))
            return (
                gr.update(interactive=not listening),  # start_btn
                gr.update(interactive=listening),      # pause_btn
            )

        with gr.Tabs():
            # -------- Profile Tab --------
            with gr.Tab("👤 User Profile"):
                gr.Markdown("### 🧠 Personalize Your Jarvin Experience")
                with gr.Row():
                    with gr.Column():
                        components['name'] = gr.Textbox(label="Your Name", placeholder="e.g., Kohei")
                        components['goal'] = gr.Textbox(label="Current Goal / Task", placeholder="e.g., Working on a Flask app")
                        components['mood'] = gr.Dropdown(
                            label="Your Current Mood",
                            choices=["Focused", "Stressed", "Curious", "Relaxed", "Tired", "Creative", "Problem-Solving"],
                            value="Focused",
                        )
                    with gr.Column():
                        components['communication_style'] = gr.Dropdown(
                            label="Preferred Communication Style",
                            choices=["Friendly", "Professional", "Casual", "Encouraging", "Direct"],
                            value="Friendly",
                        )
                        components['response_length'] = gr.Dropdown(
                            label="Preferred Response Length",
                            choices=["Concise", "Balanced", "Detailed"],
                            value="Balanced",
                        )
                components['save_btn'] = gr.Button("💾 Save Profile Settings")
                components['status'] = gr.Markdown("", elem_classes="status-text")

            # -------- Live Tab --------
            with gr.Tab("🤖 Jarvin Live"):
                gr.Markdown("### 🎙️ Live listening (noise gate + VAD)")
                with gr.Row(elem_classes="live-grid"):
                    with gr.Column(scale=1, elem_id="control_col"):
                        gr.Markdown("#### ⚙️ Controls", elem_id="controls_header")
                        # CHANGED: Markdown -> HTML to avoid markdown re-render flicker
                        components['status_banner'] = gr.HTML("&nbsp;", elem_id="status_banner")  # reserved height
                        with gr.Row(elem_classes="button_row"):
                            components['start_btn'] = gr.Button("▶ Start Listener")
                            components['stop_btn']  = gr.Button("⏸ Pause Listener")
                        with gr.Row(elem_classes="button_row"):
                            components['shutdown_btn'] = gr.Button("🛑 Shutdown Jarvin")
                        components['clear_btn'] = gr.Button("🗑️ Clear Conversation", elem_classes="clear-btn")

                    with gr.Column(scale=2, elem_id="live_col"):
                        components['transcription'] = gr.Textbox(
                            label="📝 Last Heard", placeholder="—", lines=2,
                            elem_id="transcription_box", interactive=False, show_copy_button=True
                        )
                        components['ai_reply'] = gr.Textbox(
                            label="🤖 Last Reply", placeholder="—", lines=6, max_lines=8,
                            elem_id="ai_reply_box", interactive=False, show_copy_button=True
                        )
                        # CHANGED: Markdown -> HTML to avoid markdown re-render flicker
                        components['metrics'] = gr.HTML("&nbsp;", elem_id="metrics_bar")

                with gr.Accordion("💬 Conversation History", open=False):
                    components['history_display'] = gr.Textbox(
                        label="",
                        lines=10,
                        max_lines=10,
                        interactive=False,
                        show_copy_button=True,
                        autoscroll=True,
                        elem_id="history_box",
                        elem_classes=["conversation-history"]
                    )

        # ----- Actions -----
        components['save_btn'].click(
            fn=save_user_profile,
            inputs=[
                components['name'],
                components['goal'],
                components['mood'],
                components['communication_style'],
                components['response_length'],
            ],
            outputs=[components['user_context']],
        ).then(fn=get_save_confirmation, outputs=[components['status']])

        def clear_all_conversation():
            history = clear_conversation_history()
            return "", "", history

        components['clear_btn'].click(
            fn=clear_all_conversation,
            outputs=[
                components['current_transcription'],
                components['current_reply'],
                components['conversation_memory'],
            ],
        ).then(
            fn=lambda ct, cr: (ct, cr),
            inputs=[components['current_transcription'], components['current_reply']],
            outputs=[components['transcription'], components['ai_reply']],
        )

        # Keep the history display in sync with memory
        components['conversation_memory'].change(
            fn=update_history_display,
            inputs=[components['conversation_memory']],
            outputs=[components['history_display']],
        )

        # Start/Pause/Shutdown controls
        def start_listener():
            try:
                requests.post(f"{SERVER}/start", timeout=2)
            except Exception:
                pass
            s = _get_status()
            live = _get_live()
            banner_new = _status_str(s, live) or "&nbsp;"
            start_u, pause_u = _button_updates(bool(s.get("listening", False)))
            return banner_new, start_u, pause_u

        def stop_listener():
            try:
                requests.post(f"{SERVER}/stop", timeout=2)
            except Exception:
                pass
            # After stop: listening=False
            banner_new = '<span class="status-badge status-stopped">Stopped</span>'
            start_u, pause_u = _button_updates(False)
            return banner_new, start_u, pause_u

        def shutdown_server():
            try:
                requests.post(f"{SERVER}/shutdown", timeout=2)
            except Exception:
                pass
            # Disable both buttons immediately; UI will disconnect right after
            start_u, pause_u = _button_updates(False, disabling_all=True)
            return '<span class="status-badge status-stopped">Shutting down…</span>', start_u, pause_u

        components['start_btn'].click(
            fn=start_listener,
            outputs=[components['status_banner'], components['start_btn'], components['stop_btn']]
        )
        components['stop_btn'].click(
            fn=stop_listener,
            outputs=[components['status_banner'], components['start_btn'], components['stop_btn']]
        )
        components['shutdown_btn'].click(
            fn=shutdown_server,
            outputs=[components['status_banner'], components['start_btn'], components['stop_btn']]
        )

        # Polling timer to mirror the backend loop — with anti-flicker
        _last_seen = {"transcript": None, "reply": None}
        _last_metrics_key = {"k": None}
        _last_banner = {"s": None}
        _last_processing = {"p": None}
        _last_hist_len = {"n": 0}          # NEW: track history length to avoid history redraws
        _last_btn_states = {"start": None, "pause": None}  # NEW: track button interactivity

        def tick(conversation_memory):
            s = _get_status()
            live = _get_live()

            # --- Status banner anti-flicker ---
            banner_now = _status_str(s, live) or "&nbsp;"
            if banner_now != _last_banner["s"]:
                banner_out = banner_now
                _last_banner["s"] = banner_now
            else:
                banner_out = gr.update()  # no-op

            # --- Button states (only update if interactivity actually changed) ---
            listening = bool(s.get("listening", False))
            start_u_raw, pause_u_raw = _button_updates(listening)

            def _btn_state_tuple(u):  # normalize for comparison
                return (u.get("interactive", None), u.get("visible", None), u.get("value", None))

            start_tuple = _btn_state_tuple(start_u_raw)
            pause_tuple = _btn_state_tuple(pause_u_raw)

            if start_tuple != _last_btn_states["start"]:
                start_u = start_u_raw
                _last_btn_states["start"] = start_tuple
            else:
                start_u = gr.update()

            if pause_tuple != _last_btn_states["pause"]:
                pause_u = pause_u_raw
                _last_btn_states["pause"] = pause_tuple
            else:
                pause_u = gr.update()

            # --- Transcript / Reply (only when changed) ---
            t = (live.get("transcript") or "").strip()
            r = (live.get("reply") or "").strip()

            if t != _last_seen["transcript"]:
                t_out = t
                _last_seen["transcript"] = t
            else:
                t_out = gr.update()

            if r != _last_seen["reply"]:
                r_out = r
                _last_seen["reply"] = r
            else:
                r_out = gr.update()

            # --- Metrics: update only on processing edge True -> False ---
            utt_ms = live.get("utter_ms")
            cyc_ms = live.get("cycle_ms")
            processing_now = bool(live.get("processing", False))

            metrics_out = gr.update()  # default: no change
            if _last_processing["p"] is True and processing_now is False:
                key = (
                    int(utt_ms) if utt_ms is not None else None,
                    int(cyc_ms) if cyc_ms is not None else None,
                )
                if key != _last_metrics_key["k"]:
                    parts = []
                    if utt_ms is not None:
                        parts.append(f"🎙️ utterance: {int(utt_ms)} ms")
                    if cyc_ms is not None:
                        parts.append(f"⏱️ cycle: {int(cyc_ms)} ms")
                    metrics_out = " | ".join(parts) if parts else "&nbsp;"
                    _last_metrics_key["k"] = key
            _last_processing["p"] = processing_now

            # --- Conversation history (append only when new; otherwise no-op) ---
            changed = False
            if t and (t != _last_seen["transcript"] or r != _last_seen["reply"]):
                conversation_memory = (conversation_memory or []).copy()
                conversation_memory.append(("user", t))
                if r:
                    conversation_memory.append(("assistant", r))
                changed = True

            if changed:
                hist_out = conversation_memory
                _last_hist_len["n"] = len(conversation_memory)
            else:
                hist_out = gr.update()  # no redraw of the Textbox/DOM

            return (
                banner_out,         # status_banner
                t_out,              # transcription
                r_out,              # ai_reply
                metrics_out,        # metrics
                hist_out,           # conversation_memory (only when appended)
                start_u, pause_u,   # start/stop buttons (only on state change)
            )

        # Gradio 4.44.1 Timer API
        timer = gr.Timer(value=0.5, active=True)
        timer.tick(
            fn=tick,
            inputs=[components['conversation_memory']],
            outputs=[
                components['status_banner'],
                components['transcription'],
                components['ai_reply'],
                components['metrics'],
                components['conversation_memory'],
                components['start_btn'],
                components['stop_btn'],
            ],
        )

    return demo

if __name__ == "__main__":
    demo = create_app()
    demo.launch()
