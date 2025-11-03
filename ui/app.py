# ui/app.py
from __future__ import annotations

import gradio as gr

from ui.styles import CSS
from ui.actions import (
    save_user_profile, clear_conversation_history,
    update_history_display, get_save_confirmation
)
from ui.api import (
    api_post_start, api_post_stop, api_post_shutdown,
    api_get_status, api_get_live, status_str, button_updates
)
from .poller import Poller


def create_app():
    with gr.Blocks(css=CSS) as demo:
        components = {}

        # Header
        with gr.Row():
            gr.Markdown("<h1 style='margin:0'>Jarvin - Your AI Assistant</h1>")

        # Global state
        components['user_context'] = gr.State({})
        components['conversation_memory'] = gr.State([])
        components['current_transcription'] = gr.State("")
        components['current_reply'] = gr.State("")

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
                        components['status_banner'] = gr.HTML("&nbsp;", elem_id="status_banner")
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
            api_post_start()
            s = api_get_status()
            l = api_get_live()
            banner = status_str(s, l) or "&nbsp;"
            start_u, pause_u = button_updates(bool(s.get("listening", False)))
            return banner, start_u, pause_u

        def stop_listener():
            api_post_stop()
            banner = '<span class="status-badge status-stopped">Stopped</span>'
            start_u, pause_u = button_updates(False)
            return banner, start_u, pause_u

        def shutdown_server():
            api_post_shutdown()
            start_u, pause_u = button_updates(False, disable_all=True)
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

        # Polling timer using the Poller class
        poller = Poller()
        timer = gr.Timer(value=0.5, active=True)
        timer.tick(
            fn=poller.tick,
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
