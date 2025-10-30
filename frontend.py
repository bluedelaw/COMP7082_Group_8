# frontend.py
from __future__ import annotations

import os
import requests
import gradio as gr

# Gradio frontend decoupled from local ASR: uses FastAPI /transcribe endpoint.

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


def api_transcribe(audio_path: str | None, server_url: str) -> str:
    """
    POST the recorded file to the FastAPI /transcribe endpoint and return text.
    Keeps UI independent from ASR internals (better modularity).
    """
    if not audio_path or not os.path.exists(audio_path):
        return "No audio provided."

    url = server_url.rstrip("/") + "/transcribe"
    try:
        with open(audio_path, "rb") as f:
            files = {"audio_file": (os.path.basename(audio_path), f, "audio/wav")}
            resp = requests.post(url, files=files, timeout=60)
        if resp.status_code != 200:
            return f"Server error ({resp.status_code}): {resp.text}"
        data = resp.json()
        if "transcribed_text" in data:
            return data["transcribed_text"]
        return data.get("error", "Unknown response format.")
    except Exception as e:
        return f"Request failed: {e}"


with gr.Blocks(css=css) as demo:
    with gr.Row():
        gr.Markdown("<h1 style='margin:0'>Jarvin</h1>")

    with gr.Tabs():
        with gr.Tab("User"):
            gr.Markdown("User settings will go here.")

        with gr.Tab("Jarvin"):
            gr.Markdown("Speak into your microphone and send to the backend for transcription.")

            server_url = gr.Textbox(
                label="Server URL",
                value="http://localhost:8000",
                placeholder="http://localhost:8000",
            )

            audio_input = gr.Audio(sources="microphone", type="filepath", label="Your Audio")
            transcription = gr.Textbox(label="Transcription", placeholder="Your text will appear here...")
            transcribe_btn = gr.Button("Transcribe")

            transcribe_btn.click(fn=api_transcribe, inputs=[audio_input, server_url], outputs=transcription)

if __name__ == "__main__":
    demo.launch()
