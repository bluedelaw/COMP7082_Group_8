# backend/api/schemas.py
from __future__ import annotations
from pydantic import BaseModel, ConfigDict


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TranscribeResponse(_StrictModel):
    transcribed_text: str


class ErrorResponse(_StrictModel):
    error: str


class StatusResponse(_StrictModel):
    listening: bool


class SimpleMessage(_StrictModel):
    ok: bool
    message: str


class ChatRequest(_StrictModel):
    user_text: str
    context: str | None = None
    system_instructions: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


class ChatResponse(_StrictModel):
    reply: str
