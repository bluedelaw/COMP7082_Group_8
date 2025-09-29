import gradio as gr
from audio.speech_recognition import transcribe_audio

# Custom CSS for modern look
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

    with gr.Tabs():
        with gr.Tab("User"):
            gr.Markdown("User settings will go here.")

        with gr.Tab("Jarvin"):
            gr.Markdown("Speak into your microphone and get real-time transcription!")

            audio_input = gr.Audio(sources="microphone", type="filepath", label="Your Audio")

            transcription = gr.Textbox(label="Transcription", placeholder="Your text will appear here...")

            transcribe_btn = gr.Button("Transcribe")

            transcribe_btn.click(fn=transcribe_audio, inputs=audio_input, outputs=transcription)

if __name__ == "__main__":
    demo.launch()
