"""Schémas Pydantic pour les visites (entrée/sortie)."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class VisitRead(BaseModel):
    id: UUID
    plate: str | None
    entry_gate: str
    exit_gate: str | None
    status: str
    entry_at: datetime
    exit_at: datetime | None
    entry_passage_id: UUID | None
    exit_passage_id: UUID | None

    class Config:
        from_attributes = True
