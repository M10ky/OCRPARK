"""Schémas Pydantic pour l'occupation des places."""
from datetime import datetime

from pydantic import BaseModel


class ParkingSlotRead(BaseModel):
    id: int
    label: str | None
    occupied: bool
    updated_at: datetime

    class Config:
        from_attributes = True


class ParkingSlotsSummary(BaseModel):
    slots: list[ParkingSlotRead]
    total: int
    occupied: int
    free: int
