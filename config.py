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
