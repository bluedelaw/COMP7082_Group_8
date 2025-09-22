# Jarvin AI Assistant - Project Overview

## Project Description

This project is a locally hosted AI assistant inspired by J.A.R.V.I.S. from Iron Man. It features **voice interaction**, **real-time AI responses**, and **offline capabilities**, ensuring privacy and efficiency without reliance on cloud services. The assistant leverages **Python, FastAPI, Whisper, and an LLM model** for natural language processing.

---

## Project Goals

1. **Offline AI Assistant** - No external API dependencies; fully local operation.
2. **Voice Interaction** - Real-time speech-to-text (Whisper) and text-to-speech (Piper-TTS) with optional voice conversion (RVC).
3. **LLM Integration** - Uses Mistral/Llama as the local large language model (LLM) to generate AI responses.
4. **Wake Word Activation** - Listens for a wake word (e.g., "Jarvin").
5. **Security & Privacy** - Designed for **self-hosting**, keeping all data private.

---

## Technology Stack

### Core Components

- **Backend:** FastAPI (Python-based server for AI logic)
- **AI Model:** Local LLM (Mistral, Llama, or Phi-2 via Ollama)
- **Speech-to-Text:** Whisper (Offline voice recognition)
- **Text-to-Speech:** Piper-TTS (Offline synthetic voice generation)
- **Wake Word Detection:** Porcupine (Local wake word recognition)

---

## Installation & Setup

### 1️⃣ Install Dependencies

Ensure you have Python installed, then install project dependencies:

```sh
pip install -r requirements.txt
```

### 2️⃣ Run the AI Assistant

```sh
python server.py
```

---

## Project Folder Structure

```plaintext
jarvis-ai/
│── audio/
│    ├── speech_recognition.py
│    ├── mic.py
│── backend/
│    ├── main.py
│    ├── ai_engine.py
│    ├── listener.py
│── models/                   # Local AI models
│── scripts/
│    ├── record_and_transcribe.py
│── temp/                     # recordings temporarily stored here
│── tests/                    # testing suite
│── .gitignore
│── .python-version
│── config.py
│── README.md
│── requirements.txt          # Python dependencies
│── server.py

```
