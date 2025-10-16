# backend/hw_detect.py
from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass
from typing import Optional

import psutil
import torch


@dataclass
class HardwareProfile:
    os: str
    arch: str
    cpu_cores: int
    ram_gb: float
    has_nvidia: bool
    cuda_name: Optional[str]
    vram_gb: Optional[float]
    has_mps: bool  # Apple Metal (MPS) available


def _nvidia_vram_gb() -> Optional[float]:
    # Prefer torch device props if available
    if torch.cuda.is_available():
        try:
            props = torch.cuda.get_device_properties(0)
            return round(props.total_memory / (1024 ** 3), 2)
        except Exception:
            pass
    # Fallback to nvidia-smi if present
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1.0,
        ).strip().splitlines()
        if out:
            return round(float(out[0]) / 1024.0, 2)
    except Exception:
        pass
    return None


def detect_hardware() -> HardwareProfile:
    os_name = platform.system().lower()
    arch = platform.machine().lower()
    cpu_cores = psutil.cpu_count(logical=True) or 1
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)

    has_nvidia = torch.cuda.is_available()
    vram = _nvidia_vram_gb() if has_nvidia else None
    cuda_name = None
    if has_nvidia:
        try:
            cuda_name = torch.version.cuda  # e.g., '12.1'
        except Exception:
            cuda_name = None

    has_mps = False
    try:
        has_mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    except Exception:
        has_mps = False

    return HardwareProfile(
        os=os_name,
        arch=arch,
        cpu_cores=cpu_cores,
        ram_gb=ram_gb,
        has_nvidia=has_nvidia,
        cuda_name=cuda_name,
        vram_gb=vram,
        has_mps=has_mps,
    )
