"""Modèle ParkingSlot (occupation des places, reflet des capteurs).

L'identifiant `id` correspond au champ `id` du contrat MQTT `parking/state`
(`docs/mqtt-contract.md`) : entier simple, non auto-incrémenté, seedé au
démarrage (voir `app/db/init_db.py`).
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ParkingSlot(Base):
    __tablename__ = "parking_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    label: Mapped[str | None] = mapped_column(String(16), nullable=True)
    occupied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<ParkingSlot id={self.id} occupied={self.occupied}>"
