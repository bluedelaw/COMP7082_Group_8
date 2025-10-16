# backend/llm_runtime.py
from __future__ import annotations

import logging
from functools import lru_cache
from typing import List, Dict, Optional, TYPE_CHECKING

import requests

import config as cfg
from backend.llm_model_manager import pick_model, ensure_download, GGUFModelSpec

if TYPE_CHECKING:
    # Only for type checking; not required at runtime unless llama_cpp backend is selected
    from llama_cpp import Llama  # type: ignore

log = logging.getLogger("jarvin.llmrt")


# ---------------------------
# llama.cpp (in-process) path
# ---------------------------
def _infer_chat_format(filename: str) -> Optional[str]:
    fname = filename.lower()
    if "phi-3" in fname or "phi3" in fname:
        return "phi3"
    if "mistral" in fname:
        return "mistral-instruct"
    if "neural-chat" in fname:
        return "llama-2"
    return None


@lru_cache(maxsize=1)
def _load_llama() -> Optional["Llama"]:
    """
    Singleton loader for llama-cpp-python. Returns None if unavailable or not selected.
    """
    if cfg.LLM_BACKEND.lower() != "llama_cpp":
        return None

    try:
        from llama_cpp import Llama  # type: ignore
    except Exception:
        log.warning("llama-cpp-python is not installed; local LLM (llama_cpp) disabled.")
        return None

    try:
        spec: GGUFModelSpec = pick_model()
        model_path = ensure_download(spec, models_dir=cfg.MODELS_DIR)
        chat_format = _infer_chat_format(spec.filename)
        log.info("🧠 Loading local LLM | %s (chat_format=%s)", model_path, chat_format or "default")

        llm = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_threads=None,     # auto-detect
            n_gpu_layers=0,     # CPU-only on Windows laptop
            chat_format=chat_format,
            verbose=False,
        )
        return llm
    except Exception as e:
        log.exception("Failed to load local LLM: %s", e)
        return None


def _chat_llama_cpp(system_prompt: str, user_text: str, temperature: float, max_tokens: int) -> Optional[str]:
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
        log.exception("LLM chat completion (llama_cpp) failed: %s", e)
        return None


# ---------------
# Ollama HTTP path
# ---------------
def _chat_ollama(system_prompt: str, user_text: str, temperature: float, max_tokens: int) -> Optional[str]:
    """
    Minimal Ollama /api/chat client.
    """
    url = f"{cfg.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    model = cfg.OLLAMA_MODEL
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_text.strip()},
        ],
        "options": {
            "temperature": float(temperature),
            "num_predict": int(max_tokens),
        },
        "stream": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        # Ollama returns { "message": {"role": "...", "content": "..."} , ... }
        msg = data.get("message", {})
        content = (msg.get("content") or "").strip()
        return content or None
    except Exception as e:
        log.exception("LLM chat completion (ollama) failed: %s", e)
        return None


# ---------------------
# Unified chat function
# ---------------------
def chat_completion(
    system_prompt: str,
    user_text: str,
    temperature: float = 0.7,
    max_tokens: int = 256,
) -> Optional[str]:
    backend = cfg.LLM_BACKEND.lower().strip()
    if backend == "ollama":
        # Use Ollama-specific defaults if caller passes none
        temperature = temperature if temperature is not None else cfg.OLLAMA_TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else cfg.OLLAMA_NUM_PREDICT
        return _chat_ollama(system_prompt, user_text, temperature, max_tokens)
    elif backend == "llama_cpp":
        return _chat_llama_cpp(system_prompt, user_text, temperature, max_tokens)
    else:
        log.error("Unknown LLM_BACKEND=%s", cfg.LLM_BACKEND)
        return None
