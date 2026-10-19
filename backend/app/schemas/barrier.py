"""Schémas Pydantic pour l'état de la barrière."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BarrierState(BaseModel):
    state: str | None = None
    gate: str | None = None
    reason: str | None = None
    correlation_id: str | None = None
    ack_status: str | None = None
    ts: str | None = None


class BarrierCommandRead(BaseModel):
    correlation_id: UUID
    passage_id: UUID | None
    action: str
    gate: str
    status: str
    created_at: datetime
    acked_at: datetime | None

    class Config:
        from_attributes = True


class BarrierStatus(BaseModel):
    state: BarrierState | None = None
    last_command: BarrierCommandRead | None = None
