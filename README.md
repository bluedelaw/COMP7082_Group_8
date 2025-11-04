# Jarvin AI Assistant

Local, privacy-first voice assistant inspired by J.A.R.V.I.S. It runs entirely on your machine: listens, transcribes speech with Whisper, and generates replies using a local LLM (via llama-cpp-python). No cloud APIs required.

---

## ✨ Features

- **Fully offline**: mic → VAD/noise-gate → Whisper STT → local LLM
- **Adaptive VAD** (attack/release/hangover, pre-roll, floor tracking)
- **FastAPI service** with a mounted **Gradio** UI (`/ui`)
- **Auto-provision** of a GGUF model from Hugging Face (configurable)
- Clean logging & graceful shutdowns

> Wake word and TTS (Piper) are planned but not enabled yet.

---

## 🧱 Tech Stack

- **Backend**: FastAPI, Uvicorn  
- **Speech-to-Text**: OpenAI Whisper (PyTorch)
- **LLM**: GGUF models via `llama-cpp-python`
- **Mic capture**: PyAudio  
- **Frontend (optional)**: Gradio mounted into FastAPI

---

## 📁 Project Structure

```plaintext
audio/
  mic.py
  speech_recognition.py
  vad/
    detector.py
    stream.py
    utils.py
backend/
  ai_engine.py
  audio_loop.py
  hw_detect.py
  listener.py
  llm_bootstrap.py
  llm_model_manager.py
  llm_runtime.py
  logging_setup.py
  main.py
  routes/
    chat.py
    control.py
    health.py
    live.py
    transcription.py
  schemas.py
config.py
requirements.txt
server.py
scripts/
  record_and_transcribe.py
  list-mics.py
ui/
  app.py
  api.py
  poller.py
  styles.py
models/                 # GGUF models (auto-provisioned here)
temp/                   # ephemeral audio chunks
README.md
.python-version
pyproject.toml
```

## ⚙️ Configuration

Edit `config.py` or override via env vars (prefix **`JARVIN_`**). Examples:

```bash
# Server / UI
JARVIN_SERVER_HOST=0.0.0.0
JARVIN_SERVER_PORT=8000
JARVIN_GRADIO_AUTO_OPEN=true
JARVIN_GRADIO_OPEN_DELAY_SEC=1.0

# Audio
JARVIN_SAMPLE_RATE=16000
JARVIN_RECORD_SECONDS=5
JARVIN_AMP_FACTOR=10.0

# VAD
JARVIN_VAD_CALIBRATION_SEC=1.5
JARVIN_VAD_THRESHOLD_MULT=3.0
JARVIN_VAD_THRESHOLD_ABS=200

# LLM (llama.cpp)
JARVIN_MODELS_DIR=models
JARVIN_LLM_AUTO_PROVISION=true
JARVIN_LLM_FORCE_LOGICAL_NAME=phi-3-mini-4k-instruct
JARVIN_LLM_FLAT_LAYOUT=true
JARVIN_LLM_CLEAN_VENDOR_DIRS=true

# Optional tuning
JARVIN_LLM_N_THREADS=8
JARVIN_LLM_N_GPU_LAYERS=0   # CPU-only by default
```

---

## 🚀 Quick Start

1) **Install dependencies**

    pip install -r requirements.txt

    If `llama-cpp-python` fails to build on Windows, install it via Conda first:
    conda install -c conda-forge llama-cpp-python

2) **(Optional) Editable install**  
   Lets you import `backend`, `audio`, and `ui` from anywhere while developing.

    python -m pip install -e .

3) **Run the server (FastAPI + Gradio UI)**

    python server.py

    API base: `http://127.0.0.1:8000`
    UI:       `http://127.0.0.1:8000/ui`   (auto-opens if JARVIN_GRADIO_AUTO_OPEN=true)

4) **Talk**  
   Jarvin auto-calibrates the mic, records short utterances, runs Whisper → LLM, and shows transcript & reply in the UI.

    Tips:
      - Check OS microphone permissions if nothing is captured.
      - Env overrides use the JARVIN_prefix (e.g., JARVIN_LOG_LEVEL=debug).
      - First run may auto-download a GGUF model into models/.

---

## 🧪 One-Off Transcription Test (CLI)

Record and transcribe in a loop:

```bash
python scripts/record_and_transcribe.py
```

---

## 🧰 Troubleshooting

### Whisper / PyTorch

We pin `torch==2.0.1`. For CPU-only wheels or newer CUDA stacks, reinstall from the official index:

```bash
pip install --upgrade --force-reinstall torch --index-url https://download.pytorch.org/whl/cpu
```

### Microphone (PyAudio)

- Check Windows **Privacy & security → Microphone** permissions.  
- If “No input devices found”, verify the device in Sound Settings.  
- If transcripts are empty, lower `RECORD_SECONDS`, tweak `AMP_FACTOR`, and ensure mic levels are adequate.

### ffmpeg errors

- The live loop **does not call ffmpeg** (raw PCM).  
- If you still see ffmpeg errors, confirm your `audio/speech_recognition.py` matches the current version.

## llama.cpp on Windows

- Prefer **Conda** binaries to avoid compiling `llama-cpp-python`.  
- If you compiled and it's slow, ensure it’s a **CPU build** (no GPU expected on this laptop) and that `n_threads` is sensible (auto by default).

---

## 🔒 Privacy

All audio and text stay on your machine. No external AI APIs are called during normal operation.  
(Models are fetched once from Hugging Face during setup if auto-provision is enabled.)

---

## 📜 API & Scripts

## **HTTP API**

- `GET /healthz` – liveness/readiness probe  
- `GET /status` – background listener status  
- `POST /start` / `POST /stop` – control the background listener  
- `POST /shutdown` – terminate FastAPI + UI process (graceful)  
- `GET /live` – latest transcript/reply + flags (`recording`, `processing`) and timing  
- `POST /transcribe` – one-off file transcription (multipart upload)  
- `POST /chat` – stateless chat via local LLM

## **Scripts**

- `scripts/record_and_transcribe.py` – CLI loop for quick ASR testing  
- `scripts/list-mics.py` – list working input devices at 16 kHz mono  
- `scripts/list_mics_safe.py` – enumerate input devices without opening streams

---

## 🗺️ Roadmap

- Voice Identity / Recognition
- Piper-TTS voice responses  
- Conversation memory & skills  
- Hot-swap LLM model at runtime

---
