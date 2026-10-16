"""Schémas Pydantic pour Passage."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PassageRead(BaseModel):
    id: UUID
    plate: str | None
    recognized: bool
    confidence: float | None
    allowed: bool
    source: str | None
    action: str | None
    barrier_command_sent: bool
    barrier_action: str | None
    mqtt_topic: str | None
    reason: str | None
    ocr_detections: dict | list | None
    raw_image_ref: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class PassageStats(BaseModel):
    total: int
    authorized: int
    denied: int
    recognized: int
    unrecognized: int
