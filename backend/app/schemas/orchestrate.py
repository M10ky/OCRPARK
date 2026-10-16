"""Schémas Pydantic pour orchestration."""
from pydantic import BaseModel


class OrchestrateResult(BaseModel):
    plate: str | None
    recognized: bool
    confidence: float | None
    allowed: bool
    action: str | None
    barrier_command_sent: bool
    barrier_action: str | None
    reason: str | None
    source: str
    detections: list | None = None
