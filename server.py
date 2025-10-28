# server.py
"""
Cross-platform Python launcher for the FastAPI app.
Run:
  python serve.py
"""
from __future__ import annotations

import os
import sys
import uvicorn
import config as cfg
from backend.logging_setup import init_logging

# server.py
from audio.mic import print_input_devices


if __name__ == "__main__":
    # Initialize centralized logging before starting the server (level from config.py)
    init_logging(cfg.LOG_LEVEL)

    # Reload strategy entirely from config.py; avoids env indirection
    if os.name == "nt":
        reload_flag = cfg.UVICORN_RELOAD_WINDOWS
    else:
        reload_flag = cfg.UVICORN_RELOAD_OTHERS

    try:
        uvicorn.run(
            "backend.main:app",
            host="0.0.0.0",
            port=8000,
            reload=reload_flag,
            log_level=cfg.LOG_LEVEL,
        )
    except KeyboardInterrupt:
        # Suppress noisy traceback on Ctrl+C so shutdown looks clean
        sys.exit(0)
