# backend/llm_model_manager.py
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Optional, List

try:
    # Modern API for repo downloads
    from huggingface_hub import snapshot_download
except Exception:  # pragma: no cover
    snapshot_download = None  # type: ignore

import config as cfg
from backend.hw_detect import HardwareProfile, detect_hardware


@dataclass
class GGUFModelSpec:
    logical_name: str      # e.g., "mistral-7b-instruct"
    repo_id: str           # e.g., "TheBloke/Mistral-7B-Instruct-v0.2-GGUF"
    filename: str          # e.g., "mistral-7b-instruct-v0.2.Q4_K_M.gguf"
    params_b: int          # billions of parameters (rough)
    quant: str             # e.g., "Q4_K_M"
    mem_req_gb: float      # rough RAM requirement to run


def _registry(profile: HardwareProfile) -> List[GGUFModelSpec]:
    ram = profile.ram_gb
    candidates: List[GGUFModelSpec] = []

    if ram >= 8.0:
        candidates.append(GGUFModelSpec(
            logical_name="mistral-7b-instruct",
            repo_id="TheBloke/Mistral-7B-Instruct-v0.2-GGUF",
            filename="mistral-7b-instruct-v0.2.Q4_K_M.gguf",
            params_b=7,
            quant="Q4_K_M",
            mem_req_gb=6.0,
        ))

    candidates.append(GGUFModelSpec(
        logical_name="phi-3-mini-4k-instruct",
        repo_id="microsoft/Phi-3-mini-4k-instruct-gguf",
        filename="Phi-3-mini-4k-instruct-q4.gguf",
        params_b=3,
        quant="Q4",
        mem_req_gb=4.0,
    ))

    if ram >= 8.0:
        candidates.append(GGUFModelSpec(
            logical_name="neural-chat-7b",
            repo_id="TheBloke/Neural-Chat-7B-v3-1-GGUF",
            filename="neural-chat-7b-v3-1.Q4_K_M.gguf",
            params_b=7,
            quant="Q4_K_M",
            mem_req_gb=6.0,
        ))

    pref_index = {name: i for i, name in enumerate(cfg.LLM_MODEL_PREFERENCE)}
    candidates.sort(key=lambda m: (pref_index.get(m.logical_name, 1_000), m.mem_req_gb))
    return candidates


def get_spec_by_logical_name(name: str, profile: Optional[HardwareProfile] = None) -> GGUFModelSpec:
    profile = profile or detect_hardware()
    for spec in _registry(profile):
        if spec.logical_name == name:
            return spec
    raise ValueError(f"Unknown logical model name: {name}")


def pick_model(profile: Optional[HardwareProfile] = None) -> GGUFModelSpec:
    profile = profile or detect_hardware()
    if cfg.LLM_FORCE_LOGICAL_NAME:
        return get_spec_by_logical_name(cfg.LLM_FORCE_LOGICAL_NAME, profile)
    candidates = _registry(profile)
    if not candidates:
        raise RuntimeError("No GGUF candidates available for this hardware.")
    return candidates[0]


def _validate_gguf(path: str) -> bool:
    try:
        if not os.path.exists(path):
            return False
        if os.path.getsize(path) < 10 * 1024 * 1024:  # 10 MB sanity check
            return False
        with open(path, "rb") as f:
            mag = f.read(4)
        return mag in (b"GGUF", b"gguf")
    except Exception:
        return False


def _find_file(root: str, filename: str) -> Optional[str]:
    """Find 'filename' anywhere under 'root'."""
    for dirpath, _dirnames, filenames in os.walk(root):
        if filename in filenames:
            return os.path.join(dirpath, filename)
    return None


def ensure_download(spec: GGUFModelSpec, models_dir: Optional[str] = None) -> str:
    """
    Ensure the GGUF file exists locally; return its absolute path.

    Behavior:
      - If cfg.LLM_FLAT_LAYOUT is True (default), we ensure models/<filename>.gguf exists and is valid,
        regardless of any vendor cache/snapshot structure.
      - We use snapshot_download with allow_patterns to fetch just the required file.
      - If a vendor download tree is created under models/, we optionally remove it when
        cfg.LLM_CLEAN_VENDOR_DIRS is True — but NEVER delete models/ itself.
    """
    if snapshot_download is None:
        raise RuntimeError("huggingface-hub is not installed; cannot download models.")

    models_dir = models_dir or cfg.MODELS_DIR
    os.makedirs(models_dir, exist_ok=True)

    flat_path = os.path.abspath(os.path.join(models_dir, spec.filename)) if cfg.LLM_FLAT_LAYOUT else None

    # 1) If flat file exists and validates, return it.
    if flat_path and _validate_gguf(flat_path):
        return flat_path

    # 2) Download/update a snapshot containing just this file (into models_dir).
    #    Depending on HF hub version, snapshot_root may be:
    #      - a subdirectory under models_dir (common), or
    #      - models_dir itself (when allow_patterns yields a flat copy).
    snapshot_root = snapshot_download(
        repo_id=spec.repo_id,
        local_dir=models_dir,
        allow_patterns=[spec.filename],
    )

    sr_abs = os.path.abspath(snapshot_root)
    md_abs = os.path.abspath(models_dir)

    # 3) Locate the file in the snapshot tree (could be directly under models_dir)
    src = _find_file(snapshot_root, spec.filename)
    if not src and sr_abs == md_abs:
        # If the snapshot "root" is the models dir, the file might be right there
        candidate = os.path.join(md_abs, spec.filename)
        if os.path.exists(candidate):
            src = candidate

    if not src:
        raise RuntimeError(f"Downloaded snapshot did not contain {spec.filename}: {snapshot_root}")

    # 4) Flat layout: copy/overwrite to models/<filename>
    if cfg.LLM_FLAT_LAYOUT and flat_path:
        if os.path.abspath(src) != flat_path:
            shutil.copy2(src, flat_path)

        # Validate the flat file
        if not _validate_gguf(flat_path):
            try:
                os.remove(flat_path)
            except Exception:
                pass
            raise RuntimeError(f"Downloaded model appears invalid/corrupt: {flat_path}")

        # Optional cleanup: remove only the vendor *subdirectory*, never models/ itself.
        if cfg.LLM_CLEAN_VENDOR_DIRS:
            try:
                # Only delete if snapshot_root is a subdir under models_dir (and not models_dir itself)
                if os.path.isdir(sr_abs) and os.path.commonpath([sr_abs, md_abs]) == md_abs and sr_abs != md_abs:
                    flat_dir = os.path.dirname(flat_path)
                    if os.path.normcase(sr_abs) != os.path.normcase(flat_dir):
                        shutil.rmtree(sr_abs, ignore_errors=True)
            except Exception:
                pass

            # NEW: remove models/.cache if HF created it under MODELS_DIR
            try:
                dot_cache = os.path.join(md_abs, ".cache")
                # Only remove if it truly lives under MODELS_DIR and is a directory
                if os.path.isdir(dot_cache) and os.path.commonpath([dot_cache, md_abs]) == md_abs:
                    shutil.rmtree(dot_cache, ignore_errors=True)
            except Exception:
                pass

        return flat_path

    # Non-flat layout requested: just return the snapshot file path
    if not _validate_gguf(src):
        raise RuntimeError(f"Downloaded model appears invalid/corrupt: {src}")
    return os.path.abspath(src)
