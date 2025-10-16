# Jarvin AI Assistant

Local, privacy-first voice assistant inspired by J.A.R.V.I.S. It runs entirely on your machine: listens, transcribes speech with Whisper, and generates replies with a local LLM. No cloud APIs required.

---

## ✨ Features

- **Fully offline**: STT (Whisper) + LLM run locally
- **Voice interaction**: mic capture with PyAudio
- **Pluggable LLM backends**:
  - **Ollama** (default; easiest on Windows/macOS/Linux)
  - **llama.cpp** in-process (optional; advanced)
- **FastAPI service** + optional Gradio UI
- **Clean logging & graceful shutdowns**

> Wake word and TTS (Piper) are planned but not enabled yet.

---

## 🧱 Tech Stack

- **Backend**: FastAPI, Uvicorn  
- **Speech-to-Text**: OpenAI Whisper (PyTorch)
- **LLM**:  
  - Default: **Ollama** models (e.g. `phi3:mini`, `mistral`, `llama3`)  
  - Optional: **GGUF** models via `llama-cpp-python`
- **Mic capture**: PyAudio  
- **Frontend (optional)**: Gradio

---

## 📁 Project Structure

```plaintext
audio/
  mic.py
  speech_recognition.py
backend/
  ai_engine.py
  hw_detect.py
  listener.py
  llm_bootstrap.py
  llm_model_manager.py
  llm_runtime.py
  logging_setup.py
  main.py
frontend.py
models/                 # GGUF models for llama.cpp backend (not needed for Ollama)
scripts/
  record_and_transcribe.py
temp/                   # ephemeral audio chunks
config.py
requirements.txt
server.py
README.md
.python-version
```

---

## ⚙️ Configuration

Edit `config.py`. Key flags:

```python
# Select backend: "ollama" (default) or "llama_cpp"
LLM_BACKEND: str = "ollama"

# --- Ollama settings (default path) ---
OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
OLLAMA_MODEL: str = "phi3:mini"     # try "mistral" or "llama3" later
OLLAMA_TEMPERATURE: float = 0.7
OLLAMA_NUM_PREDICT: int = 256

# --- llama.cpp path (optional advanced backend) ---
MODELS_DIR: str = "models"          # where GGUFs live
LLM_AUTO_PROVISION: bool = True     # auto-download GGUFs when using llama_cpp
LLM_FORCE_LOGICAL_NAME: str = "phi-3-mini-4k-instruct"
LLM_FLAT_LAYOUT: bool = True
LLM_CLEAN_VENDOR_DIRS: bool = True

# Audio
SAMPLE_RATE = 16_000
RECORD_SECONDS = 5
AMP_FACTOR = 10.0

# Server / logging
LOG_LEVEL = "info"
```

---

## 🚀 Quick Start (Recommended: Ollama)

1. **Install Python deps**

   ```bash
   pip install -r requirements.txt
   ```

1. **Install Ollama**

   - Windows (winget):

     ```powershell
     winget install Ollama.Ollama
     ```

   - Or download from [Ollama](https://ollama.com)

1. **Start Ollama service** (in a separate terminal)

   ```bash
   ollama serve
   ```

1. **Pull a small model (CPU-friendly)**

   ```bash
   ollama pull phi3:mini
   ```

   > You can try others later: `ollama pull mistral`, `ollama pull llama3`  
   > If you change the model, update `OLLAMA_MODEL` in `config.py`.

1. **Run Jarvin**

   ```bash
   python server.py
   ```

1. **Talk!**  
   The listener records short chunks, transcribes with Whisper, and sends the text to your local LLM. Replies are logged.

---

## 🧪 One-Off Transcription Test (CLI)

Record and transcribe in a loop:

```bash
python scripts/record_and_transcribe.py
```

---

## 🖥️ Optional UI (Gradio)

Launch the simple demo UI:

```bash
python frontend.py
```

---

## 🔧 Optional: In-Process LLM via llama.cpp (Advanced)

This runs the model inside your Python process using `llama-cpp-python`. On Windows this can involve native builds.

1. **Switch backend**

   ```python
   # config.py
   LLM_BACKEND = "llama_cpp"
   ```

1. **Install llama-cpp-python**

   - **Conda (recommended on Windows)**:

     ```bash
     conda install -c conda-forge llama-cpp-python
     ```

   > **Note:** Using pip often requires CMake + MSVC to build from source.

1. **Run the server** to auto-provision a GGUF into `models/`:

   ```bash
   python server.py
   ```

   > To select a different GGUF, adjust `LLM_FORCE_LOGICAL_NAME` or the registry in `backend/llm_model_manager.py`.

---

## 🧰 Troubleshooting

### Whisper / PyTorch

- We pin `torch==2.0.1`. For CPU-only wheels or newer CUDA stacks, reinstall from the official index or:

  ```bash
  pip install --upgrade --force-reinstall torch --index-url https://download.pytorch.org/whl/cpu
  ```

### Microphone (PyAudio)

- Check Windows **Privacy & security → Microphone** permissions.
- If “No input devices found”, verify the device in Sound Settings.
- If transcripts are empty, lower `RECORD_SECONDS`, tweak `AMP_FACTOR`, and ensure your mic level is adequate.

### ffmpeg errors

- The live loop **no longer calls ffmpeg** (we feed raw PCM).  
  If you still see ffmpeg errors, confirm your `audio/speech_recognition.py` matches the current version.

### Ollama connection

- Make sure the service is up:

  ```bash
  ollama serve
  curl http://127.0.0.1:11434/api/tags
  ```

- Ensure `OLLAMA_BASE_URL` matches.

### llama-cpp on Windows

- Prefer Conda binaries to avoid compiling.
- If compiled and slow, ensure it’s a CPU build (no GPU expected on this laptop) and that `n_threads` is sensible (auto by default).

---

## 🔒 Privacy

All audio and text stay on your machine. No external AI APIs are called during normal operation.  
(Models are fetched once from Ollama’s registry or Hugging Face during setup.)

---

## 📜 API & Scripts

- `POST /transcribe` – one-off file transcription (multipart upload)  
- `POST /start`, `POST /stop`, `GET /status` – control the background listener  
- `scripts/record_and_transcribe.py` – CLI loop for quick testing

---

## 🗺️ Roadmap

- Wake word detection (Porcupine)  
- Piper-TTS voice responses  
- Conversation memory & skills  
- Hot-swap LLM model at runtime

---

## 🤝 Contributing

- Use Python 3.11 (see `.python-version`)  
- Keep PRs small and focused  
- Add helpful logs; avoid noisy tracebacks on shutdown

---

## 📄 License

MIT (or your preferred license)
