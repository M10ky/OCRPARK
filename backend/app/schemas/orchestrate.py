"""Schémas Pydantic pour orchestration."""
from pydantic import BaseModel


class OrchestrateResult(BaseModel):
    plate: str | None
    recognized: bool
    confidence: float | None
    authorized: bool = False
    allowed: bool
    action: str | None
    gate: str = "entry"
    barrier_command_sent: bool
    barrier_action: str | None
    barrier_ack_status: str | None = None
    total_slots: int | None = None
    free_slots: int | None = None
    reason: str | None
    source: str
    correlation_id: str | None = None
    detections: list | None = None
