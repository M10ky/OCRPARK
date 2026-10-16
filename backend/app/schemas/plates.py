"""Schémas Pydantic pour AllowedPlate."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AllowedPlateBase(BaseModel):
    plate: str = Field(min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=255)
    active: bool = True


class AllowedPlateCreate(AllowedPlateBase):
    pass


class AllowedPlateUpdate(BaseModel):
    plate: str | None = Field(default=None, min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=255)
    active: bool | None = None


class AllowedPlateRead(AllowedPlateBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
