# backend/schemas.py
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

# ----- Chat API -----
class ChatRequest(BaseModel):
    user_text: str
    # Optional fields to let the client pass context/styles without hard coupling
    context: str | None = None
    system_instructions: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None

class ChatResponse(BaseModel):
    reply: str
