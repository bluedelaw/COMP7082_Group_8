# ui/components.py
from __future__ import annotations
import gradio as gr


def init_state(components: dict) -> None:
    """Create global Gradio States used across tabs."""
    components["user_context"] = gr.State({})
    components["conversation_memory"] = gr.State([])  # active conversation history

    # Hold the conversation dropdown value to prevent flicker on refresh (currently unused but harmless)
    components["conversation_dropdown_value"] = gr.State(None)

    # Hidden state that changes only when a NEW utterance is appended
    components["live_seq"] = gr.State(None)

    # Hidden states for utterance/response timestamps (raw values, not rendered text)
    components["utter_ts_state"] = gr.State(None)
    components["reply_ts_state"] = gr.State(None)

    # Hidden state for metrics text + its own sequence id
    components["metrics_state"] = gr.State(None)
    components["metrics_seq"] = gr.State(None)


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

                # ---- Conversations panel ----
                with gr.Accordion("🗂️ Conversations", open=True):
                    components["conv_subtitle"] = gr.Markdown("", elem_classes="status-text")
                    with gr.Row():
                        components["conversation_dropdown"] = gr.Dropdown(
                            label="Select",
                            choices=[],
                            value=None,
                            interactive=True,
                        )
                    with gr.Row():
                        components["new_conv_title"] = gr.Textbox(
                            label="New conversation title",
                            placeholder="e.g., Trip planning",
                        )
                        components["new_conv_btn"] = gr.Button("➕ New")
                    with gr.Row():
                        components["rename_conv_title"] = gr.Textbox(
                            label="Rename to…",
                            placeholder="e.g., Weekend tasks",
                        )
                        components["rename_conv_btn"] = gr.Button("✏️ Rename")
                        components["delete_conv_btn"] = gr.Button(
                            "🗑️ Delete",
                            elem_classes="clear-btn",
                        )

                components["clear_btn"] = gr.Button(
                    "🧹 Clear This Conversation",
                    elem_classes="clear-btn",
                )

            # Live / conversation column
            with gr.Column(scale=2, elem_id="live_col"):
                gr.Markdown("#### 💬 Conversation")
                # Single unified conversation log (ChatGPT-style bubbles)
                components["chat_history"] = gr.Markdown(
                    value="No conversation history yet.",
                    elem_id="history_box",
                    elem_classes=["conversation-history"],
                )
                components["tts_audio"] = gr.Audio(
                    label="🔊 Spoken Reply",
                    autoplay=True,
                    interactive=False,
                )

                # Rendered timestamps for utterance and response
                components["utter_ts_md"] = gr.Markdown("&nbsp;", elem_classes="status-text")
                components["reply_ts_md"] = gr.Markdown("&nbsp;", elem_classes="status-text")

                # Metrics bar (decoupled from polling via metrics_state/metrics_seq)
                components["metrics"] = gr.HTML("&nbsp;", elem_id="metrics_bar")

        # 🎤 Microphone controls
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
