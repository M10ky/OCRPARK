"""Modèle BarrierCommand (fiabilisation commande barrière : ack + timeout).

`correlation_id` est l'identifiant publié dans `parking/barrier/command` et
attendu en retour dans `barrier/state` (voir `docs/mqtt-contract.md`). Il vaut
`Passage.id`. Le statut permet de tracer une commande restée sans ACK.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

BARRIER_CMD_PENDING = "pending"
BARRIER_CMD_ACKNOWLEDGED = "acknowledged"
BARRIER_CMD_TIMEOUT = "timeout"


class BarrierCommand(Base):
    __tablename__ = "barrier_commands"

    correlation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    passage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("passages.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(8), nullable=False)
    gate: Mapped[str] = mapped_column(String(8), nullable=False)
    # "pending" | "acknowledged" | "timeout"
    status: Mapped[str] = mapped_column(
        String(16), default=BARRIER_CMD_PENDING, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    acked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<BarrierCommand id={self.correlation_id} status={self.status}>"
