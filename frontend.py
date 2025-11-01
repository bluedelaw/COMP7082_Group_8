import gradio as gr
from frontend.components import CSS
from frontend.handlers import process_audio, save_user_profile, clear_conversation_history, update_history_display, get_save_confirmation
from memory.conversation import get_conversation_history

def create_app():
    with gr.Blocks(css=CSS) as demo:
        # Create the interface and get all components
        components = {}
        
        with gr.Row():
            gr.Markdown("<h1 style='margin:0'>Jarvin - Your AI Assistant</h1>")

        components['user_context'] = gr.State({})
        components['conversation_memory'] = gr.State([])
        # Add state to store current transcription and reply
        components['current_transcription'] = gr.State("")
        components['current_reply'] = gr.State("")

        with gr.Tabs():
            # User Profile Tab
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
            
            # Jarvin Chat Tab
            with gr.Tab("🤖 Jarvin Chat"):
                gr.Markdown("### 🎙️ Chat with Jarvin")
                gr.Markdown("**Click the microphone, speak, then click stop - processing starts immediately**", elem_classes="recording-status")
                
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("#### ⚙️ Settings")
                        components['use_memory'] = gr.Checkbox(
                            label="Use Conversation Memory",
                            value=True,
                            info="Remember previous messages in this session"
                        )
                        
                        components['response_style'] = gr.Radio(
                            label="Response Style",
                            choices=["balanced", "concise", "detailed", "encouraging"],
                            value="balanced",
                            info="Adjust how Jarvin responds"
                        )
                        
                        components['clear_btn'] = gr.Button("🗑️ Clear Conversation", elem_classes="clear-btn")
                        
                    with gr.Column(scale=2):
                        components['audio_input'] = gr.Audio(
                            sources="microphone", 
                            type="filepath", 
                            label="🎤 Click to Record",
                            interactive=True,
                            show_download_button=False
                        )

                        components['transcription'] = gr.Textbox(
                            label="📝 Your Message",
                            placeholder="Transcription will appear here...",
                            lines=2
                        )
                        
                        components['ai_reply'] = gr.Textbox(
                            label="🤖 Jarvin's Response",
                            placeholder="Jarvin's reply will appear here...",
                            lines=6,
                            max_lines=8
                        )
                
                # Conversation history display - made scrollable
                with gr.Accordion("💬 Conversation History", open=False):
                    components['history_display'] = gr.Textbox(
                        label="",
                        lines=8,
                        max_lines=12,
                        interactive=False,
                        show_copy_button=True,  # Add copy button for convenience
                        autoscroll=True  # Auto-scroll to bottom
                    )

        def process_and_store_audio(audio_path, user_context, use_memory, response_style, current_transcription, current_reply, conversation_memory):
            """Process audio and store results in state"""
            if audio_path:  # Only process if we have new audio
                text, reply, history = process_audio(audio_path, user_context, use_memory, response_style)
                # Store the new results in state and return all 5 required outputs
                return text, reply, history, text, reply
            else:
                # No new audio, return the stored values (all 5 outputs)
                # Use the current conversation_memory state to preserve history
                return current_transcription, current_reply, conversation_memory, current_transcription, current_reply

        def update_display_from_state(current_transcription, current_reply):
            """Update the display with stored values"""
            return current_transcription, current_reply

        # Process audio and store results
        components['audio_input'].change(
            fn=process_and_store_audio,
            inputs=[
                components['audio_input'],
                components['user_context'], 
                components['use_memory'],
                components['response_style'],
                components['current_transcription'],
                components['current_reply'],
                components['conversation_memory']  # Add this input
            ],
            outputs=[
                components['current_transcription'],  # Store transcription in state
                components['current_reply'],          # Store reply in state
                components['conversation_memory'],    # Update conversation history
                components['transcription'],          # Update display
                components['ai_reply']                # Update display
            ]
        ).then(
            # Clear audio input after processing
            fn=lambda: None,
            outputs=[components['audio_input']]
        )

        # Initialize display with stored values
        demo.load(
            fn=update_display_from_state,
            inputs=[
                components['current_transcription'],
                components['current_reply']
            ],
            outputs=[
                components['transcription'],
                components['ai_reply']
            ]
        )
        
        components['save_btn'].click(
            fn=save_user_profile,
            inputs=[
                components['name'],
                components['goal'],
                components['mood'],
                components['communication_style'],
                components['response_length']
            ],
            outputs=[components['user_context']]
        ).then(
            fn=get_save_confirmation,
            outputs=[components['status']]
        )
        
        def clear_all_conversation():
            """Clear conversation history and current results"""
            history = clear_conversation_history()
            return "", "", history

        components['clear_btn'].click(
            fn=clear_all_conversation,
            outputs=[
                components['current_transcription'],
                components['current_reply'],
                components['conversation_memory']
            ]
        ).then(
            fn=update_display_from_state,
            inputs=[
                components['current_transcription'],
                components['current_reply']
            ],
            outputs=[
                components['transcription'],
                components['ai_reply']
            ]
        )
        
        components['conversation_memory'].change(
            fn=update_history_display,
            inputs=[components['conversation_memory']],
            outputs=[components['history_display']]
        )
    
    return demo

if __name__ == "__main__":
    demo = create_app()
    demo.launch()