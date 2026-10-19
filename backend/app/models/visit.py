"""Modèle Visit (visites entrée/sortie d'un véhicule).

Une visite est ouverte par un événement `entry` et fermée par un événement
`exit` (topic `parking/events`, voir `docs/mqtt-contract.md`). Le lien vers
`Passage` est optionnel : il rattache la décision d'orchestration (autorisation)
à la visite quand elle est connue.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

VISIT_STATUS_INSIDE = "inside"
VISIT_STATUS_CLOSED = "closed"


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plate: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    entry_gate: Mapped[str] = mapped_column(String(8), nullable=False)
    exit_gate: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # "inside" (en cours) ou "closed" (terminée)
    status: Mapped[str] = mapped_column(
        String(16), default=VISIT_STATUS_INSIDE, index=True, nullable=False
    )
    entry_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    exit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    entry_passage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("passages.id", ondelete="SET NULL"),
        nullable=True,
    )
    exit_passage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("passages.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<Visit id={self.id} plate={self.plate} status={self.status}>"
