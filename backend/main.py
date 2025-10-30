# backend/main.py
from __future__ import annotations

import logging

from backend.logging_setup import init_logging
import config as cfg
from backend.app import create_app

# Initialize logging once, then build the app via factory (clean construction).
init_logging(cfg.LOG_LEVEL)
log = logging.getLogger("jarvin")

app = create_app()
