# ui/components.py
from __future__ import annotations

import gradio as gr


def init_state(components: dict) -> None:
    """Create global Gradio States used across tabs."""
    components["user_context"] = gr.State({})
    components["conversation_memory"] = gr.State([])
    components["current_transcription"] = gr.State("")
    components["current_reply"] = gr.State("")


def build_header() -> None:
    with gr.Row():
        gr.Markdown("<h1 style='margin:0'>Jarvin - Your AI Assistant</h1>")


def build_profile_tab(components: dict) -> None:
    with gr.Tab("👤 User Profile"):
        gr.Markdown("### 🧠 Personalize Your Jarvin Experience")
        with gr.Row():
            with gr.Column():
                components["name"] = gr.Textbox(label="Your Name", placeholder="e.g., Kohei")
                components["goal"] = gr.Textbox(label="Current Goal / Task", placeholder="e.g., Working on a Flask app")
                components["mood"] = gr.Dropdown(
                    label="Your Current Mood",
                    choices=["Focused", "Stressed", "Curious", "Relaxed", "Tired", "Creative", "Problem-Solving"],
                    value="Focused",
                )
            with gr.Column():
                components["communication_style"] = gr.Dropdown(
                    label="Preferred Communication Style",
                    choices=["Friendly", "Professional", "Casual", "Encouraging", "Direct"],
                    value="Friendly",
                )
                components["response_length"] = gr.Dropdown(
                    label="Preferred Response Length",
                    choices=["Concise", "Balanced", "Detailed"],
                    value="Balanced",
                )
        components["save_btn"] = gr.Button("💾 Save Profile Settings")
        components["status"] = gr.Markdown("", elem_classes="status-text")


def build_live_tab(components: dict) -> None:
    with gr.Tab("🤖 Jarvin Live"):
        gr.Markdown("### 🎙️ Live listening (noise gate + VAD)")
        with gr.Row(elem_classes="live-grid"):
            # Controls column
            with gr.Column(scale=1, elem_id="control_col"):
                gr.Markdown("#### ⚙️ Controls", elem_id="controls_header")
                components["status_banner"] = gr.HTML("&nbsp;", elem_id="status_banner")
                with gr.Row(elem_classes="button_row"):
                    components["start_btn"] = gr.Button("▶ Start Listener")
                    components["stop_btn"] = gr.Button("⏸ Pause Listener")
                with gr.Row(elem_classes="button_row"):
                    components["shutdown_btn"] = gr.Button("🛑 Shutdown Jarvin")
                components["clear_btn"] = gr.Button("🗑️ Clear Conversation", elem_classes="clear-btn")

            # Live column
            with gr.Column(scale=2, elem_id="live_col"):
                components["transcription"] = gr.Textbox(
                    label="📝 Last Heard",
                    placeholder="—",
                    lines=2,
                    elem_id="transcription_box",
                    interactive=False,
                    show_copy_button=True,
                )
                components["ai_reply"] = gr.Textbox(
                    label="🤖 Last Reply",
                    placeholder="—",
                    lines=6,
                    max_lines=8,
                    elem_id="ai_reply_box",
                    interactive=False,
                    show_copy_button=True,
                )
                # Autoplay synthesized TTS when a new reply arrives
                components["tts_audio"] = gr.Audio(
                    label="🔊 Spoken Reply",
                    autoplay=True,
                    interactive=False,
                )
                components["metrics"] = gr.HTML("&nbsp;", elem_id="metrics_bar")

        # 🎤 Microphone controls (single source of truth)
        with gr.Accordion("🎤 Microphone", open=False):
            components["device_current"] = gr.Markdown("", elem_classes="status-text")
            with gr.Row():
                components["device_dropdown"] = gr.Dropdown(
                    label="Input device",
                    choices=[],   # populated on load
                    value=None,
                    interactive=True,
                )
                components["device_refresh_btn"] = gr.Button("🔄 Refresh", scale=0)

        with gr.Accordion("💬 Conversation History", open=False):
            components["history_display"] = gr.Textbox(
                label="",
                lines=10,
                max_lines=10,
                interactive=False,
                show_copy_button=True,
                # removed unsupported `autoscroll` for Gradio 4.44.x
                elem_id="history_box",
                elem_classes=["conversation-history"],
            )
