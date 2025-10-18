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
# Local LLM (llama.cpp) settings
# ---------------------------------------------------------------------------
MODELS_DIR: str = "models"
LLM_BACKEND: str = "llama_cpp"   # <— back to llama.cpp

# Auto-download GGUF model on startup
LLM_AUTO_PROVISION: bool = True

# Pick a logical model from our registry (see llm_model_manager.py)
LLM_FORCE_LOGICAL_NAME: str = "phi-3-mini-4k-instruct"

# Preference order when not forced
LLM_MODEL_PREFERENCE: list[str] = [
    "mistral-7b-instruct",
    "phi-3-mini-4k-instruct",
    "neural-chat-7b",
]

# Download/layout behavior
LLM_FLAT_LAYOUT: bool = True
LLM_CLEAN_VENDOR_DIRS: bool = True
