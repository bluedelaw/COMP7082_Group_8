# ui/app.py
from __future__ import annotations

import gradio as gr

from ui.styles import CSS
from ui.components import build_header, build_profile_tab, build_live_tab, init_state
from ui.handlers import bind_profile_actions, bind_live_actions, _live_stream  # stream generator


def create_app():
    with gr.Blocks(css=CSS) as demo:
        # central component registry
        components: dict[str, gr.Component] = {}

        # global state (kept identical keys as before)
        init_state(components)

        # header
        build_header()

        # tabs & contents
        with gr.Tabs():
            build_profile_tab(components)
            build_live_tab(components)

        # wire events
        bind_profile_actions(components)
        bind_live_actions(components)

        # ✅ Populate microphone list and current selection on page load
        demo.load(
            fn=components["_init_devices_fn"],   # set by bind_profile_actions
            outputs=[components["device_dropdown"], components["device_current"]],
            show_progress=False,
        )

        # ✅ Auto-attach the live stream on page load
        load_stream_evt = demo.load(
            fn=_live_stream,
            inputs=[components["conversation_memory"]],
            outputs=[
                components["transcription"],
                components["ai_reply"],
                components["metrics"],
                components["conversation_memory"],
            ],
            show_progress=False,
            concurrency_limit=1,  # one stream per session
        )

        # Ensure Stop/Shutdown also cancel the load-attached stream
        components["stop_btn"].click(
            fn=lambda: None,
            cancels=[load_stream_evt],
            concurrency_limit=4,
        )
        components["shutdown_btn"].click(
            fn=lambda: None,
            cancels=[load_stream_evt],
            concurrency_limit=2,
        )

        # enable queue with default settings (Gradio 4.x)
        demo.queue()

    return demo


if __name__ == "__main__":
    demo = create_app()
    demo.launch()
