# backend/llm_runtime.py
from __future__ import annotations

import logging
from functools import lru_cache
from typing import List, Dict, Optional, TYPE_CHECKING

import config as cfg
from backend.llm_model_manager import pick_model, ensure_download, GGUFModelSpec

if TYPE_CHECKING:
    # Available to the type checker; not imported at runtime if package missing
    from llama_cpp import Llama  # type: ignore

log = logging.getLogger("jarvin.llmrt")


def _infer_chat_format(filename: str) -> Optional[str]:
    fname = filename.lower()
    # Phi-3 Instruct uses ChatML; llama-cpp ships a "chatml" handler
    if "phi-3" in fname or "phi3" in fname:
        return "chatml"
    if "mistral" in fname:
        return "mistral-instruct"
    if "neural-chat" in fname:
        return "llama-2"
    return None


@lru_cache(maxsize=1)
def _load_llama() -> Optional["Llama"]:
    """
    Singleton loader for the local LLM (llama-cpp-python).
    Ensures the GGUF exists and loads it with a sensible context size.
    """
    try:
        from llama_cpp import Llama  # type: ignore
    except Exception:
        log.warning("llama-cpp-python is not installed; local LLM disabled.")
        return None

    try:
        spec: GGUFModelSpec = pick_model()
        model_path = ensure_download(spec, models_dir=cfg.MODELS_DIR)
        chat_format = _infer_chat_format(spec.filename)
        log.info("🧠 Loading local LLM | %s (chat_format=%s)", model_path, chat_format or "default")

        llm = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_threads=None,     # let library pick a good default
            n_gpu_layers=0,     # CPU-only (Windows laptop without CUDA)
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
