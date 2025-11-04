# backend/llm/bootstrap.py
from __future__ import annotations
import logging

import config as cfg
from backend.util.hw_detect import detect_hardware
from backend.llm.model_manager import pick_model, ensure_download, GGUFModelSpec

log = logging.getLogger("jarvin.llm")

async def provision_llm() -> str | None:
    s = cfg.settings
    if not s.llm_auto_provision:
        log.info("LLM auto-provision disabled.")
        return None

    try:
        profile = detect_hardware()
        log.info(
            "🧩 HW profile | os=%s arch=%s cpu_cores=%d ram=%.2fGB nvidia=%s vram=%sGB mps=%s",
            profile.os, profile.arch, profile.cpu_cores, profile.ram_gb,
            str(profile.has_nvidia), str(profile.vram_gb), str(profile.has_mps),
        )

        spec: GGUFModelSpec = pick_model(profile)
        log.info("📦 LLM spec selected | logical=%s repo=%s file=%s",
                 spec.logical_name, spec.repo_id, spec.filename)

        path = ensure_download(spec, models_dir=s.models_dir)
        log.info("✅ LLM model ready | %s", path)
        return path
    except Exception as e:
        log.exception("LLM provisioning failed: %s", e)
        return None
