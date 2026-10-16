"""Schémas Pydantic pour orchestration."""
from pydantic import BaseModel


class OrchestrateResult(BaseModel):
    plate: str | None
    recognized: bool
    confidence: float | None
    allowed: bool
    action: str | None
    gate: str = "entry"
    barrier_command_sent: bool
    barrier_action: str | None
    reason: str | None
    source: str
    correlation_id: str | None = None
    detections: list | None = None
