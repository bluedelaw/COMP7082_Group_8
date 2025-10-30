# backend/util/paths.py
from __future__ import annotations

import os
import uuid

import config as cfg


def ensure_temp_dir() -> str:
    """
    Ensure the configured temp directory exists. Return absolute path.
    """
    path = os.path.abspath(cfg.TEMP_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def temp_path(name: str) -> str:
    """
    Deterministic file path inside the temp directory (e.g., 'live_utt.wav').
    """
    root = ensure_temp_dir()
    return os.path.join(root, name)


def temp_unique_path(prefix: str = "up_", suffix: str = ".tmp") -> str:
    """
    Generate a unique randomized path inside the temp directory for uploads, etc.
    """
    root = ensure_temp_dir()
    return os.path.join(root, f"{prefix}{uuid.uuid4().hex}{suffix}")
