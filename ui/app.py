# ui/app.py
from __future__ import annotations

import gradio as gr

from ui.styles import CSS
from ui.components import build_header, build_profile_tab, build_live_tab, init_state
from ui.handlers import bind_profile_actions, bind_live_actions
from ui.actions import update_history_display, load_user_profile_fields
from ui.poller import Poller


def create_app():
    with gr.Blocks(css=CSS) as demo:
        components: dict[str, gr.Component] = {}
        init_state(components)

        build_header()
        with gr.Tabs():
            build_profile_tab(components)
            build_live_tab(components)

        # Wire actions for Profile + Live
        bind_profile_actions(components)
        bind_live_actions(components)

        # --- Single page-load initializer (devices + saved profile) ---
        def _init_page():
            # 1) Device UI (choices + selected + label)
            choices_update, label = components["_init_devices_fn"]()  # returns (Dropdown.update, label)
            # 2) Saved profile prefill
            name, goal, mood, style, length, status = load_user_profile_fields()
            return (
                choices_update,   # device dropdown update (choices + selected)
                label,            # device_current Markdown
                name, goal, mood, style, length, status  # profile fields + status text
            )

        demo.load(
            fn=_init_page,
            outputs=[
                components["device_dropdown"],
                components["device_current"],
                components["name"],
                components["goal"],
                components["mood"],
                components["communication_style"],
                components["response_length"],
                components["status"],
            ],
            show_progress=False,
        )

        # ✅ Single polling loop drives EVERYTHING (banner, textboxes, metrics, history).
        poller = Poller()
        timer = gr.Timer(value=0.75, active=True)  # 750ms feels snappy without spamming
        tick_evt = timer.tick(
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
                components["tts_audio"],
            ],
            show_progress=False,
            concurrency_limit=1,
        )

        # 🔁 Render the history panel **every** tick using the updated memory
        tick_evt.then(
            fn=update_history_display,
            inputs=[components["conversation_memory"]],
            outputs=[components["history_display"]],
            show_progress=False,
        )

        demo.queue()

    return demo


if __name__ == "__main__":
    demo = create_app()
    demo.launch()
