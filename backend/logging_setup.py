# backend/logging_setup.py
from __future__ import annotations

import logging
import sys
from typing import Optional

_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

def init_logging(level: Optional[str] = None) -> None:
    """
    Initialize root logger to match the project's original console format:
    'YYYY-mm-dd HH:MM:SS,ms | LEVEL | message'
    - Single StreamHandler to stdout
    - No changes to uvicorn/fastapi loggers (preserves their 'INFO: ...' lines)
    - No JSON, no file handlers
    """
    lvl_name = (level or "info").lower()
    lvl = _LEVELS.get(lvl_name, logging.INFO)

    root = logging.getLogger()
    # Clear existing handlers to avoid duplicate lines
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    root.addHandler(handler)
    root.setLevel(lvl)
