# backend/llm_runtime.py
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import List, Dict, Optional, TYPE_CHECKING

import config as cfg
from backend.llm_model_manager import pick_model, ensure_download, GGUFModelSpec

if TYPE_CHECKING:
    # Available to the type checker; not imported at runtime if package missing
    from llama_cpp import Llama  # type: ignore

log = logging.getLogger("jarvin.llmrt")

# Prefer an explicit mapping keyed by logical model name (more stable than filename heuristics).
_CHAT_FORMAT_BY_LOGICAL: Dict[str, str] = {
    "phi-3-mini-4k-instruct": "chatml",
    "mistral-7b-instruct": "mistral-instruct",
    "neural-chat-7b": "llama-2",
}


def _infer_chat_format(spec: GGUFModelSpec) -> Optional[str]:
    """
    Decide chat formatting for llama.cpp based primarily on the logical model name.
    Fall back to filename heuristics if unknown.
    """
    fmt = _CHAT_FORMAT_BY_LOGICAL.get(spec.logical_name)
    if fmt:
        return fmt

    # Fallback heuristic (kept for robustness)
    fname = spec.filename.lower()
    if "phi-3" in fname or "phi3" in fname:
        return "chatml"
    if "mistral" in fname:
        return "mistral-instruct"
    if "neural-chat" in fname:
        return "llama-2"
    return None


def _env_int(name: str, default: int) -> int:
    try:
        v = os.getenv(name)
        return int(v) if v is not None else default
    except Exception:
        return default


@lru_cache(maxsize=1)
def _load_llama() -> Optional["Llama"]:
    """
    Singleton loader for the local LLM (llama-cpp-python).
    Ensures the GGUF exists and loads it with a sensible context size.
    Uses environment overrides for threads and GPU layers to avoid hard-coding:
      - JARVIN_LLM_N_THREADS (int, default: library default)
      - JARVIN_LLM_N_GPU_LAYERS (int, default: 0)
    """
    try:
        from llama_cpp import Llama  # type: ignore
    except Exception:
        log.warning("llama-cpp-python is not installed; local LLM disabled.")
        return None

    try:
        spec: GGUFModelSpec = pick_model()
        model_path = ensure_download(spec, models_dir=cfg.MODELS_DIR)
        chat_format = _infer_chat_format(spec)

        # Runtime tuning from environment (keeps config.py smaller and optional)
        n_threads_env = os.getenv("JARVIN_LLM_N_THREADS")
        n_threads = int(n_threads_env) if n_threads_env and n_threads_env.isdigit() else None
        n_gpu_layers = _env_int("JARVIN_LLM_N_GPU_LAYERS", 0)

        log.info(
            "🧠 Loading local LLM | path=%s chat_format=%s n_ctx=%d n_threads=%s n_gpu_layers=%d",
            model_path,
            chat_format or "default",
            4096,
            str(n_threads) if n_threads is not None else "auto",
            n_gpu_layers,
        )

        llm = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_threads=n_threads,     # let library pick a good default if None
            n_gpu_layers=n_gpu_layers,
            chat_format=chat_format,
            verbose=False,
        )
        return llm
    except Exception as e:
        log.exception("Failed to load local LLM: %s", e)
        return None


def chat_completion(
    system_prompt: str,
    user_text: str,
    temperature: float = 0.7,
    max_tokens: int = 256,
) -> Optional[str]:
    """
    Simple chat wrapper around llama.cpp. Returns the model's text or None on failure.
    """
    llm = _load_llama()
    if llm is None:
        return None

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": user_text.strip()},
    ]

    try:
        out = llm.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=None,
        )
        return out["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.exception("LLM chat completion failed: %s", e)
        return None
