# config.py
"""
Global configuration for Jarvin.

This module now uses a Pydantic BaseSettings class so values can be overridden
via environment variables (prefix: JARVIN_). For example:
  JARVIN_SAMPLE_RATE=44100
  JARVIN_LOG_LEVEL=debug
  JARVIN_CORS_ALLOW_ORIGINS='["http://localhost:3000"]'
  JARVIN_SERVER_HOST=0.0.0.0
  JARVIN_SERVER_PORT=8000
  JARVIN_GRADIO_AUTO_OPEN=true
  JARVIN_GRADIO_OPEN_DELAY_SEC=1.0

Backwards compatibility:
- All previous module-level constants still exist and are populated from
  `settings = Settings()`. Existing imports like `import config as cfg; cfg.SAMPLE_RATE`
  continue to work unchanged.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ---------------- Audio / capture ----------------
    sample_rate: int = 16_000
    chunk: int = 1024
    record_seconds: int = 5
    amp_factor: float = 10.0

    # Temp dir for ephemeral files (overwritten each cycle)
    temp_dir: str = "temp"

    # Whisper model selection
    # None -> auto-select based on GPU VRAM; otherwise set: "tiny"|"base"|"small"|"medium"|"large"
    whisper_model_size: Optional[str] = None

    # CORS (dev-friendly; restrict in prod)
    cors_allow_origins: List[str] = Field(default_factory=lambda: ["*"])

    # Logging
    log_level: str = "info"

    # When not persisting, delete the raw WAV after amplifying (saves I/O)
    delete_raw_after_amplify: bool = True

    # Listener / startup behavior
    initial_listener_delay: float = 0.2
    # NEW: start the background mic listener on boot. Set False for “deaf on boot”.
    start_listener_on_boot: bool = True

    # Uvicorn reload behavior
    uvicorn_reload_windows: bool = False
    uvicorn_reload_others: bool = True

    # NEW: control Uvicorn access logs (GET/POST 200 lines). Default: off.
    uvicorn_access_log: bool = False

    # ---------------- Local LLM (llama.cpp) settings ----------------
    models_dir: str = "models"
    llm_backend: str = "llama_cpp"

    # Auto-download GGUF model on startup
    llm_auto_provision: bool = True

    # Pick a logical model from our registry (see llm_model_manager.py)
    llm_force_logical_name: str = "phi-3-mini-4k-instruct"

    # Preference order when not forced
    llm_model_preference: List[str] = Field(
        default_factory=lambda: [
            "mistral-7b-instruct",
            "phi-3-mini-4k-instruct",
            "neural-chat-7b",
        ]
    )

    # Download/layout behavior
    llm_flat_layout: bool = True
    llm_clean_vendor_dirs: bool = True

    # ---------------- Voice Activity / Noise Gate ----------------
    # Initial background calibration duration
    vad_calibration_sec: float = 1.5

    # Trigger threshold relative to the (smoothed) noise floor
    # Effective threshold = max(VAD_THRESHOLD_ABS, noise_floor_rms * VAD_THRESHOLD_MULT)
    vad_threshold_mult: float = 3.0
    vad_threshold_abs: float = 200.0   # absolute RMS guardrail (int16 scale)

    # Debounce timing (ms)
    vad_attack_ms: int = 120           # how long above threshold to start
    vad_release_ms: int = 350          # how long below threshold to consider ended
    vad_hangover_ms: int = 200         # grace after dips below threshold during speech

    # Recording guards
    vad_pre_roll_ms: int = 300         # audio to prepend before trigger
    vad_min_utterance_ms: int = 250    # discard ultra-short bursts
    vad_max_utterance_sec: float = 30  # safety cutoff

    # Optional level conditioning
    normalize_to_dbfs: Optional[float] = -3.0  # None to disable; otherwise peak normalize to this dBFS

    # -------- VAD logging --------
    # Heartbeat while idle (ms). 0 disables.
    vad_heartbeat_ms: int = 1000

    # Log an utterance START/END banner and a one-line summary per utterance.
    vad_log_transitions: bool = True

    # Optional detailed stats (DEBUG level) every N frames; 0 disables.
    vad_log_stats_every_n_frames: int = 0  # e.g., 10 to log ~every ~640ms with CHUNK=1024@16k

    # Cap how often threshold changes are logged during idle (ms)
    vad_log_threshold_changes_ms: int = 3000

    # TTY live status (single updating line while idle)
    vad_tty_status: bool = True  # set False to disable in-place status updates

    # -------- VAD behavior toggles --------
    # Use instantaneous RMS for trigger decisions (more responsive) vs smoothed envelope
    vad_use_instant_rms_for_trigger: bool = True

    # Clamp noise floor during calibration and adaptation (int16 RMS units)
    vad_floor_min: float = 20.0
    vad_floor_max: float = 4000.0

    # Require a margin below threshold before adapting floor (prevents chasing near-speech)
    vad_floor_adapt_margin: float = 0.90

    # -------- Voice shutdown behavior --------
    # If False (default), a single shutdown hotword immediately exits.
    # If True, require a second voice confirmation.
    voice_shutdown_confirm: bool = False

    # ---------------- Server / Gradio UI ----------------
    # Where uvicorn binds; the UI is mounted into the same app.
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # Control Gradio behavior without requiring users to set env vars.
    gradio_use_cdn: bool = True
    gradio_analytics_enabled: bool = False
    # Where to mount the UI. Default "/ui" (safer than root).
    gradio_mount_path: str = "/ui"

    # Auto-open a browser to the mounted Gradio UI on server start.
    gradio_auto_open: bool = True
    gradio_open_delay_sec: float = 1.0

    class Config:
        env_prefix = "JARVIN_"
        case_sensitive = False

    # Pydantic v2-style validator
    @field_validator("log_level", mode="before")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"debug", "info", "warning", "error", "critical"}
        vv = str(v).lower().strip()
        return vv if vv in allowed else "info"


# Instantiate settings once
settings = Settings()

# --------------------------------------------------------------------------
# Backwards-compatible module-level symbols (mirror previous constants)
# --------------------------------------------------------------------------
# Audio / capture
SAMPLE_RATE: int = settings.sample_rate
CHUNK: int = settings.chunk
RECORD_SECONDS: int = settings.record_seconds
AMP_FACTOR: float = settings.amp_factor

# Temp dir
TEMP_DIR: str = settings.temp_dir

# Whisper
WHISPER_MODEL_SIZE: Optional[str] = settings.whisper_model_size

# CORS
CORS_ALLOW_ORIGINS: List[str] = settings.cors_allow_origins

# Logging
LOG_LEVEL: str = settings.log_level

# File lifecycle
DELETE_RAW_AFTER_AMPLIFY: bool = settings.delete_raw_after_amplify

# Listener / startup
INITIAL_LISTENER_DELAY: float = settings.initial_listener_delay
START_LISTENER_ON_BOOT: bool = settings.start_listener_on_boot  # NEW

# Uvicorn reload + access logs
UVICORN_RELOAD_WINDOWS: bool = settings.uvicorn_reload_windows
UVICORN_RELOAD_OTHERS: bool = settings.uvicorn_reload_others
UVICORN_ACCESS_LOG: bool = settings.uvicorn_access_log  # NEW

# Local LLM
MODELS_DIR: str = settings.models_dir
LLM_BACKEND: str = settings.llm_backend
LLM_AUTO_PROVISION: bool = settings.llm_auto_provision
LLM_FORCE_LOGICAL_NAME: str = settings.llm_force_logical_name
LLM_MODEL_PREFERENCE: List[str] = settings.llm_model_preference
LLM_FLAT_LAYOUT: bool = settings.llm_flat_layout
LLM_CLEAN_VENDOR_DIRS: bool = settings.llm_clean_vendor_dirs

# VAD thresholds and behavior
VAD_CALIBRATION_SEC: float = settings.vad_calibration_sec
VAD_THRESHOLD_MULT: float = settings.vad_threshold_mult
VAD_THRESHOLD_ABS: float = settings.vad_threshold_abs
VAD_ATTACK_MS: int = settings.vad_attack_ms
VAD_RELEASE_MS: int = settings.vad_release_ms
VAD_HANGOVER_MS: int = settings.vad_hangover_ms
VAD_PRE_ROLL_MS: int = settings.vad_pre_roll_ms
VAD_MIN_UTTERANCE_MS: int = settings.vad_min_utterance_ms
VAD_MAX_UTTERANCE_SEC: float = settings.vad_max_utterance_sec
NORMALIZE_TO_DBFS: Optional[float] = settings.normalize_to_dbfs

# VAD logging
VAD_HEARTBEAT_MS: int = settings.vad_heartbeat_ms
VAD_LOG_TRANSITIONS: bool = settings.vad_log_transitions
VAD_LOG_STATS_EVERY_N_FRAMES: int = settings.vad_log_stats_every_n_frames
VAD_LOG_THRESHOLD_CHANGES_MS: int = settings.vad_log_threshold_changes_ms
VAD_TTY_STATUS: bool = settings.vad_tty_status

# VAD toggles
VAD_USE_INSTANT_RMS_FOR_TRIGGER: bool = settings.vad_use_instant_rms_for_trigger
VAD_FLOOR_MIN: float = settings.vad_floor_min
VAD_FLOOR_MAX: float = settings.vad_floor_max
VAD_FLOOR_ADAPT_MARGIN: float = settings.vad_floor_adapt_margin

# Voice shutdown
VOICE_SHUTDOWN_CONFIRM: bool = settings.voice_shutdown_confirm

# ---------------- Server / Gradio UI (module-level mirrors) -------------
SERVER_HOST: str = settings.server_host
SERVER_PORT: int = settings.server_port

GRADIO_USE_CDN: bool = settings.gradio_use_cdn
GRADIO_ANALYTICS_ENABLED: bool = settings.gradio_analytics_enabled
GRADIO_MOUNT_PATH: str = settings.gradio_mount_path

GRADIO_AUTO_OPEN: bool = settings.gradio_auto_open
GRADIO_OPEN_DELAY_SEC: float = settings.gradio_open_delay_sec
