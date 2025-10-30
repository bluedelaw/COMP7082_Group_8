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
