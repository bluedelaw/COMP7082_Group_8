# ui/app.py
from __future__ import annotations

import gradio as gr

from ui.styles import CSS
from ui.components import build_header, build_profile_tab, build_live_tab, init_state
from ui.handlers import bind_profile_actions, bind_live_actions
from ui.actions import update_history_display
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

        # Populate microphone list + current selection on page load
        demo.load(
            fn=components["_init_devices_fn"],   # set by bind_profile_actions
            outputs=[components["device_dropdown"], components["device_current"]],
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
