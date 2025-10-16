# config.py
"""Global configuration for Jarvin."""
from __future__ import annotations

# Audio / capture
SAMPLE_RATE: int = 16_000
CHUNK: int = 1024
RECORD_SECONDS: int = 5
AMP_FACTOR: float = 10.0

# Temp dir for ephemeral files (overwritten each cycle)
TEMP_DIR: str = "temp"

# Whisper model selection
# None -> auto-select based on GPU VRAM; otherwise set: "tiny"|"base"|"small"|"medium"|"large"
WHISPER_MODEL_SIZE: str | None = None

# CORS (dev-friendly; restrict in prod)
CORS_ALLOW_ORIGINS: list[str] = ["*"]

# Logging
LOG_LEVEL: str = "info"

# When not persisting, delete the raw WAV after amplifying (saves I/O)
DELETE_RAW_AFTER_AMPLIFY: bool = True

# Listener / startup behavior
INITIAL_LISTENER_DELAY: float = 0.2

# Uvicorn reload behavior
UVICORN_RELOAD_WINDOWS: bool = False
UVICORN_RELOAD_OTHERS: bool = True

# ---------------------------------------------------------------------------
# Local LLM bootstrap / backend selection
# ---------------------------------------------------------------------------
MODELS_DIR: str = "models"

# Choose backend: "ollama" (recommended on Windows CPU) or "llama_cpp"
LLM_BACKEND: str = "ollama"

# If you switch back to llama_cpp, you can auto-provision GGUFs from HF Hub:
LLM_AUTO_PROVISION: bool = True

# Logical model choice used by llama_cpp path; for Ollama we use OLLAMA_MODEL below
LLM_FORCE_LOGICAL_NAME: str = "phi-3-mini-4k-instruct"

# Preference order when not forced (llama_cpp path)
LLM_MODEL_PREFERENCE: list[str] = [
    "mistral-7b-instruct",
    "phi-3-mini-4k-instruct",
    "neural-chat-7b",
]

# Download/layout behavior for llama_cpp path
LLM_FLAT_LAYOUT: bool = True
LLM_CLEAN_VENDOR_DIRS: bool = True

# ---------------------------------------------------------------------------
# Ollama settings
# ---------------------------------------------------------------------------
# Base URL where ollama serve is running
OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
# Model tag to use with Ollama (must be pulled with `ollama pull ...`)
# Good small CPU choice:
OLLAMA_MODEL: str = "phi3:mini"
# Optional response settings
OLLAMA_TEMPERATURE: float = 0.7
OLLAMA_NUM_PREDICT: int = 256
