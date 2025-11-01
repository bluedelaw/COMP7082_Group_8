import gradio as gr
from audio.speech_recognition import transcribe_audio
from backend.ai_engine import generate_reply, JarvinConfig
import config as cfg

# Jarvin system prompt
JARVIN_SYSTEM_PROMPT = """
You are Jarvin, a friendly and helpful AI assistant. 
Your tone should be warm, encouraging, and positive.
Always be supportive and provide useful guidance.
"""

# Function that ties transcription + AI reply together
def process_audio(audio_path: str, user_context: dict):
    if not audio_path:
        return "No audio input detected.", "No reply generated."

    text = transcribe_audio(audio_path).strip()
    if not text:
        return "(empty transcription)", "No reply generated."

    cfg_ai = JarvinConfig()
    context_text = ""
    if user_context:
        context_text = (
            f"User Name: {user_context.get('name', 'Unknown')}\n"
            f"Goal: {user_context.get('goal', 'None')}\n"
            f"Mood: {user_context.get('mood', 'Neutral')}\n\n"
        )

    # Combine Jarvin's identity with user context and query
    prompt = f"{JARVIN_SYSTEM_PROMPT}\n\n{context_text}User said: {text}"
    reply = generate_reply(prompt, cfg=cfg_ai)

    return text, reply


css = """
body {
    background-color: #1f1f2e;
    color: #f5f5f5;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.gradio-container {
    border-radius: 12px;
    padding: 20px;
}

.tab-content {
    background-color: #2c2c3e;
    border-radius: 8px;
    padding: 20px;
    margin-top: 10px;
}

.gr-button {
    background-color: #4f46e5;
    color: white;
    border-radius: 8px;
    border: none;
    padding: 10px 20px;
    font-weight: bold;
}

.gr-button:hover {
    background-color: #6366f1;
}

.gradio-tabs button {
    background-color: #3b3b4e;
    color: #f5f5f5;
    border-radius: 8px 8px 0 0;
    padding: 10px 20px;
    margin-right: 2px;
    font-weight: bold;
}

.gradio-tabs button:focus {
    outline: none;
    background-color: #57577f;
}
"""


with gr.Blocks(css=css) as demo:
    with gr.Row():
        gr.Markdown("<h1 style='margin:0'>Jarvin</h1>")

    user_context = gr.State({})

    with gr.Tabs():
        # ===== USER TAB =====
        with gr.Tab("User"):
            gr.Markdown("### 🧠 Set Jarvin's Context")
            name = gr.Textbox(label="Your Name", placeholder="e.g., Kohei")
            goal = gr.Textbox(label="Current Goal / Task", placeholder="e.g., Working on a Flask app")
            mood = gr.Dropdown(
                label="Your Mood",
                choices=["Focused", "Stressed", "Curious", "Relaxed", "Tired"],
                value="Focused",
            )

            save_btn = gr.Button("💾 Save Context")

            # When user clicks Save, store info in state
            def save_user_context(name, goal, mood):
                return {"name": name, "goal": goal, "mood": mood}

            save_btn.click(save_user_context, inputs=[name, goal, mood], outputs=user_context)
            gr.Markdown("*(Jarvin will use this context in future replies.)*")

        # ===== JARVIN TAB =====
        with gr.Tab("Jarvin"):
            gr.Markdown("### 🎙️ Speak to Jarvin")
            gr.Markdown("**Click record, speak, then click stop - Jarvin will respond automatically**")
            
            audio_input = gr.Audio(
                sources="microphone", 
                type="filepath", 
                label="🎤 Your Voice",
                interactive=True
            )

            with gr.Row():
                transcription = gr.Textbox(label="📝 Transcription")
                ai_reply = gr.Textbox(
                    label="🤖 Jarvin's Reply",
                    lines=5,  # Increased from default to make it larger
                    max_lines=10  # Allow it to grow even more if needed
                )

            # Use .change instead of .stop for immediate processing
            audio_input.change(
                fn=process_audio,
                inputs=[audio_input, user_context],
                outputs=[transcription, ai_reply],
            )

if __name__ == "__main__":
    demo.launch()