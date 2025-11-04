# ui/app.py
from __future__ import annotations

import gradio as gr

from ui.styles import CSS
from ui.components import build_header, build_profile_tab, build_live_tab, init_state
from ui.handlers import bind_profile_actions, bind_live_actions, bind_polling


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
        bind_polling(components)

    return demo


if __name__ == "__main__":
    demo = create_app()
    demo.launch()
