# backend/api/routes/chat.py
from __future__ import annotations

import logging
from fastapi import APIRouter
from backend.api.schemas import ChatRequest, ChatResponse, ErrorResponse
from backend.ai_engine import generate_reply, JarvinConfig

log = logging.getLogger("jarvin.routes.chat")
router = APIRouter(tags=["chat"])

@router.post("/chat", response_model=ChatResponse | ErrorResponse)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse | ErrorResponse:
    """
    Stateless chat endpoint. The client can pass already-constructed context.
    Server selects/generates the reply via local LLM; on failure returns ErrorResponse.
    """
    text = (payload.user_text or "").strip()
    if not text:
        return ErrorResponse(error="empty user_text")

    # Optional style knobs: keep simple/consistent with ai_engine defaults
    cfg = JarvinConfig(
        system_instructions=(payload.system_instructions or JarvinConfig().system_instructions),
        temperature=payload.temperature if payload.temperature is not None else JarvinConfig().temperature,
        max_tokens=payload.max_tokens if payload.max_tokens is not None else JarvinConfig().max_tokens,
    )

    # Compose final input seen by the model
    prompt = text if not payload.context else f"{payload.context.strip()}\n\n{ text }"

    try:
        reply = generate_reply(prompt, cfg=cfg)
        return ChatResponse(reply=reply)
    except Exception as e:
        log.exception("Chat generation failed: %s", e)
        return ErrorResponse(error="chat generation failed")
