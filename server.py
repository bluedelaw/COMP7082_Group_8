# server.py
"""
Cross-platform Python launcher for the FastAPI app.
Run:
  python server.py
"""
from __future__ import annotations

import os
import sys
import uvicorn

import config as cfg
from backend.logging_setup import init_logging
from backend.app import create_app


def main() -> int:
    # Initialize centralized logging before starting the server (level from config.py)
    init_logging(cfg.LOG_LEVEL)

    # Build the FastAPI app via the factory (side-effect free wiring)
    app = create_app()

    # Reload strategy from config.py; avoids env indirection
    if os.name == "nt":
        reload_flag = cfg.UVICORN_RELOAD_WINDOWS
    else:
        reload_flag = cfg.UVICORN_RELOAD_OTHERS

    try:
        uvicorn.run(
            app=app,
            host="0.0.0.0",
            port=8000,
            reload=reload_flag,
            log_level=cfg.LOG_LEVEL,
        )
        return 0
    except KeyboardInterrupt:
        # Suppress noisy traceback on Ctrl+C so shutdown looks clean
        return 0


if __name__ == "__main__":
    sys.exit(main())
