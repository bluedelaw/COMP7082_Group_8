# backend/api/schemas.py
from __future__ import annotations
from pydantic import BaseModel

class TranscribeResponse(BaseModel):
    transcribed_text: str

class ErrorResponse(BaseModel):
    error: str

class StatusResponse(BaseModel):
    listening: bool

class SimpleMessage(BaseModel):
    ok: bool
    message: str

class ChatRequest(BaseModel):
    user_text: str
    context: str | None = None
    system_instructions: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None

class ChatResponse(BaseModel):
    reply: str
