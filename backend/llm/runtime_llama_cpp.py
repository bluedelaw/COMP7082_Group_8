# backend/llm/runtime_llama_cpp.py
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import List, Dict, Optional, TYPE_CHECKING

import config as cfg
from backend.llm.model_manager import pick_model, ensure_download, GGUFModelSpec

if TYPE_CHECKING:
    from llama_cpp import Llama  # type: ignore

log = logging.getLogger("jarvin.llmrt")

_CHAT_FORMAT_BY_LOGICAL: Dict[str, str] = {
    "phi-3-mini-4k-instruct": "chatml",
    "mistral-7b-instruct": "mistral-instruct",
    "neural-chat-7b": "llama-2",
}

def _infer_chat_format(spec: GGUFModelSpec) -> Optional[str]:
    fmt = _CHAT_FORMAT_BY_LOGICAL.get(spec.logical_name)
    if fmt:
        return fmt
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
    try:
        from llama_cpp import Llama  # type: ignore
    except Exception:
        log.warning("llama-cpp-python is not installed; local LLM disabled.")
        return None

    try:
        spec: GGUFModelSpec = pick_model()
        model_path = ensure_download(spec, models_dir=cfg.settings.models_dir)
        chat_format = _infer_chat_format(spec)

        n_threads_env = os.getenv("JARVIN_LLM_N_THREADS")
        n_threads = int(n_threads_env) if n_threads_env and n_threads_env.isdigit() else None

        llm_use_gpu = cfg.settings.llm_use_gpu
        n_gpu_layers = 0
        gpu_message = "GPU not used"

        if llm_use_gpu is True or llm_use_gpu is None:
            try:
                import torch
                if torch.cuda.is_available():
                    total_vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
                    # Heuristic: ~0.75 GB per layer
                    n_gpu_layers = min(int(total_vram_gb // 0.75), 32)
                    if llm_use_gpu is True:
                        n_gpu_layers = _env_int("JARVIN_LLM_N_GPU_LAYERS", n_gpu_layers)
                    gpu_message = f"GPU detected ({total_vram_gb:.1f} GB VRAM), using {n_gpu_layers} layers."
                else:
                    gpu_message = "No GPU detected. Running on CPU."
            except ImportError:
                gpu_message = "PyTorch not installed; cannot detect GPU. Running on CPU."
        else:
            gpu_message = "GPU disabled by configuration. Running on CPU."

        print(f"🖥️ {gpu_message}")  # <-- added print statement

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
            n_threads=n_threads,
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

