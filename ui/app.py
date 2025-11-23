# ui/app.py
from __future__ import annotations

import gradio as gr

from ui.styles import CSS
from ui.components import build_header, build_profile_tab, build_live_tab, init_state
from ui.handlers import bind_profile_actions, bind_live_actions
from ui.actions import update_history_display, load_user_profile_fields, get_conversation_menu
from ui.poller import Poller
from memory.conversation import get_conversation_history


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

        # --- Single page-load initializer (devices + saved profile + conversations + chat log) ---
        def _init_page():
            # 1) Device UI (choices + selected + label)
            choices_update, label = components["_init_devices_fn"]()  # returns (Dropdown.update, label)

            # 2) Saved profile prefill
            name, goal, mood, style, length, status = load_user_profile_fields()

            # 3) Conversations dropdown
            conv_choices, conv_selected, conv_subtitle = get_conversation_menu()

            # 4) Active conversation history -> state + rendered chat log
            history = get_conversation_history()
            chat_html = update_history_display(history)

            return (
                choices_update,   # device dropdown update (choices + selected)
                label,            # device_current Markdown
                name, goal, mood, style, length, status,  # profile fields + status text
                gr.update(choices=conv_choices, value=conv_selected),  # conversations dropdown
                conv_subtitle,
                history,          # conversation_memory state
                chat_html,        # chat_history markdown
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
                components["conversation_dropdown"],
                components["conv_subtitle"],
                components["conversation_memory"],
                components["chat_history"],
            ],
            show_progress=False,
        )

        # ✅ Single polling loop: DOES NOT touch chat_history directly.
        poller = Poller()
        timer = gr.Timer(value=0.75, active=True)  # 750ms feels snappy without spamming
        timer.tick(
            fn=poller.tick,
            inputs=[components["conversation_memory"]],
            outputs=[
                components["status_banner"],        # status banner
                components["metrics"],              # metrics
                components["conversation_memory"],  # updated history (list[(role, msg)])
                components["start_btn"],            # start button state
                components["stop_btn"],             # stop button state
                components["tts_audio"],            # TTS audio URL
                components["live_seq"],             # hidden seq state
            ],
            show_progress=False,
            concurrency_limit=1,
        )

        # 🔁 Render the unified chat log ONLY when live_seq actually changes.
        #    This decouples the chat div from the raw polling frequency.
        components["live_seq"].change(
            fn=update_history_display,
            inputs=[components["conversation_memory"]],
            outputs=[components["chat_history"]],
            show_progress=False,
        )

        demo.queue()

    return demo


if __name__ == "__main__":
    demo = create_app()
    demo.launch()
