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

        def _status_str(s: dict) -> str:
            return "🟢 **Listening**" if s.get("listening") else "🔴 **Stopped**"

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

            # -------- Live Tab (noise gate + VAD) --------
            with gr.Tab("🤖 Jarvin Live"):
                gr.Markdown("### 🎙️ Live listening (noise gate + VAD)")
                # Make the row a stable grid via CSS class to avoid flex-wrap jitters
                with gr.Row(elem_classes="live-grid"):
                    with gr.Column(scale=1, elem_id="control_col"):
                        gr.Markdown("#### ⚙️ Controls", elem_id="controls_header")
                        components['status_banner'] = gr.Markdown(" ", elem_id="status_banner")  # reserved height
                        with gr.Row(elem_classes="button_row"):
                            components['start_btn'] = gr.Button("▶ Start Listener")
                            components['stop_btn']  = gr.Button("⛔ Stop Listener")
                        components['clear_btn'] = gr.Button("🗑️ Clear Conversation", elem_classes="clear-btn")

                    with gr.Column(scale=2, elem_id="live_col"):
                        # Fixed-height textboxes (CSS pins the inner <textarea> heights)
                        components['transcription'] = gr.Textbox(
                            label="📝 Last Heard", placeholder="—", lines=2,
                            elem_id="transcription_box", interactive=False, show_copy_button=True
                        )
                        components['ai_reply'] = gr.Textbox(
                            label="🤖 Last Reply", placeholder="—", lines=6, max_lines=8,
                            elem_id="ai_reply_box", interactive=False, show_copy_button=True
                        )
                        # Metrics bar with reserved space
                        components['metrics'] = gr.Markdown(" ", elem_id="metrics_bar")

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

        # Start/Stop controls
        def start_listener():
            try:
                requests.post(f"{SERVER}/start", timeout=2)
            except Exception:
                pass
            s = _get_status()
            return _status_str(s) or " "

        def stop_listener():
            try:
                requests.post(f"{SERVER}/stop", timeout=2)
            except Exception:
                pass
            s = _get_status()
            return _status_str(s) or " "

        components['start_btn'].click(fn=start_listener, outputs=[components['status_banner']])
        components['stop_btn'].click(fn=stop_listener, outputs=[components['status_banner']])

        # Polling timer to mirror the backend loop
        _last_seen = {"transcript": None, "reply": None}

        def tick(conversation_memory):
            s = _get_status()
            live = _get_live()
            banner = _status_str(s) or " "

            t = (live.get("transcript") or "").strip()
            r = (live.get("reply") or "").strip()
            utt_ms = live.get("utter_ms")
            cyc_ms = live.get("cycle_ms")

            # Reserve metrics space; keep one-line, no-wrap
            metrics = ""
            if utt_ms is not None or cyc_ms is not None:
                parts = []
                if utt_ms is not None:
                    parts.append(f"🎙️ utterance: **{int(utt_ms)} ms**")
                if cyc_ms is not None:
                    parts.append(f"⏱️ cycle: **{int(cyc_ms)} ms**")
                metrics = " | ".join(parts)
            if not metrics:
                metrics = "&nbsp;"  # non-breaking space to hold height

            # Append to history only when new content arrives
            if t and (t != _last_seen["transcript"] or r != _last_seen["reply"]):
                conversation_memory = conversation_memory or []
                conversation_memory.append(("user", t))
                if r:
                    conversation_memory.append(("assistant", r))
                _last_seen["transcript"] = t
                _last_seen["reply"] = r

            return banner, t, r, metrics, conversation_memory

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
            ],
        )

    return demo

if __name__ == "__main__":
    demo = create_app()
    demo.launch()
