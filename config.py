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
LLM_BACKEND: str = "llama_cpp"

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

# -------- Voice Activity / Noise Gate (frames are ~20–64 ms depending on CHUNK) --------
# Initial background calibration duration
VAD_CALIBRATION_SEC: float = 1.5

# Trigger threshold relative to the (smoothed) noise floor
# Effective threshold = max(VAD_THRESHOLD_ABS, noise_floor_rms * VAD_THRESHOLD_MULT)
VAD_THRESHOLD_MULT: float = 3.0
VAD_THRESHOLD_ABS: float = 200.0   # absolute RMS guardrail (int16 scale)

# Debounce timing (ms)
VAD_ATTACK_MS: int = 120           # how long above threshold to start
VAD_RELEASE_MS: int = 350          # how long below threshold to consider ended
VAD_HANGOVER_MS: int = 200         # grace after dips below threshold during speech

# Recording guards
VAD_PRE_ROLL_MS: int = 300         # audio to prepend before trigger
VAD_MIN_UTTERANCE_MS: int = 250    # discard ultra-short bursts
VAD_MAX_UTTERANCE_SEC: float = 30  # safety cutoff

# Optional level conditioning
NORMALIZE_TO_DBFS: float | None = -3.0  # None to disable; otherwise peak normalize to this dBFS

# -------- VAD logging --------
# Heartbeat while idle (ms). 0 disables.
VAD_HEARTBEAT_MS: int = 1000

# Log an utterance START/END banner and a one-line summary per utterance.
VAD_LOG_TRANSITIONS: bool = True

# Optional detailed stats (DEBUG level) every N frames; 0 disables.
VAD_LOG_STATS_EVERY_N_FRAMES: int = 0  # e.g., 10 to log ~every ~640ms with CHUNK=1024@16k

# Cap how often threshold changes are logged during idle (ms)
VAD_LOG_THRESHOLD_CHANGES_MS: int = 3000

# TTY live status (single updating line while idle)
VAD_TTY_STATUS: bool = True  # set False to disable in-place status updates

# -------- VAD behavior toggles --------
# Use instantaneous RMS for trigger decisions (more responsive) vs smoothed envelope
VAD_USE_INSTANT_RMS_FOR_TRIGGER: bool = True

# Clamp noise floor during calibration and adaptation (int16 RMS units)
VAD_FLOOR_MIN: float = 20.0
VAD_FLOOR_MAX: float = 4000.0

# Require a margin below threshold before adapting floor (prevents chasing near-speech)
VAD_FLOOR_ADAPT_MARGIN: float = 0.90

# -------- Voice shutdown behavior --------
# If False (default), a single shutdown hotword immediately exits.
# If True, require a second voice confirmation.
VOICE_SHUTDOWN_CONFIRM: bool = False
