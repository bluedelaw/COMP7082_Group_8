# server.py
"""
Cross-platform Python launcher for the FastAPI app.
Run:
  python serve.py
"""
from __future__ import annotations

import uvicorn
import config as cfg

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # turn to False in production
        log_level=cfg.LOG_LEVEL,
    )
