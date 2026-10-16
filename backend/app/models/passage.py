"""Modèle Passage (historique des passages)."""
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Passage(Base):
    __tablename__ = "passages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plate: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    recognized: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    # VARCHAR(32) : "orchestrator:upload" fait 19 caractères (VARCHAR(16) tronquait).
    # Migration manuelle sur une base existante (create_all n'altère pas) :
    #   ALTER TABLE passages ALTER COLUMN source TYPE VARCHAR(32);
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str | None] = mapped_column(String(8), nullable=True)
    barrier_command_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    barrier_action: Mapped[str | None] = mapped_column(String(8), nullable=True)
    mqtt_topic: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ocr_detections: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    raw_image_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    def __repr__(self) -> str:
        return f"<Passage plate={self.plate} allowed={self.allowed} source={self.source}>"
