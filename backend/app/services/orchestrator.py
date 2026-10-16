"""Orchestrateur : détection→OCR→décision→commande barrière."""
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.allowed_plate import AllowedPlate
from app.models.passage import Passage
from app.services.mqtt import mqtt_client
from app.services.ocr_client import normalize_plate

settings = get_settings()


class OrchestratorResult:
    def __init__(self, **data: Any) -> None:
        self.__dict__.update(data)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__


async def decide_and_act(
    session: AsyncSession,
    ocr_result: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    best = ocr_result.get("best") if "best" in ocr_result else None
    if best is None and "plate" in ocr_result:
        best = {
            "text": ocr_result.get("plate"),
            "confidence": ocr_result.get("confidence"),
        }

    plate_raw = (best or {}).get("text") if best else ocr_result.get("plate")
    confidence = (best or {}).get("confidence") if best else ocr_result.get("confidence")
    normalized = normalize_plate(plate_raw)
    recognized = normalized is not None and len(normalized) > 0

    allowed = False
    reason = "Non reconnu" if not recognized else "Plaque non autorisée"
    if recognized:
        stmt = select(AllowedPlate).where(AllowedPlate.plate == normalized, AllowedPlate.active.is_(True))
        res = await session.execute(stmt)
        ap = res.scalar_one_or_none()
        if ap:
            allowed = True
            reason = "Plaque autorisée"

    action = "open" if allowed else "deny"
    barrier_action = "open" if allowed else None
    barrier_command_sent = False

    if allowed and mqtt_client.is_connected:
        cmd = {
            "action": "open",
            "plate": normalized,
            "reason": reason,
            "source": source,
            "correlation_id": normalized,
        }
        await mqtt_client.publish(settings.MQTT_TOPIC_BARRIER_COMMAND, cmd)
        barrier_command_sent = True

    passage = Passage(
        plate=normalized,
        recognized=recognized,
        confidence=float(confidence) if confidence is not None else None,
        allowed=allowed,
        source=source,
        action=action,
        barrier_command_sent=barrier_command_sent,
        barrier_action=barrier_action,
        mqtt_topic=settings.MQTT_TOPIC_BARRIER_COMMAND if barrier_command_sent else None,
        reason=reason,
        ocr_detections=ocr_result.get("detections"),
    )
    session.add(passage)
    await session.commit()
    await session.refresh(passage)

    return {
        "plate": normalized,
        "recognized": recognized,
        "confidence": float(confidence) if confidence is not None else None,
        "allowed": allowed,
        "action": action,
        "barrier_command_sent": barrier_command_sent,
        "barrier_action": barrier_action,
        "reason": reason,
        "source": source,
        "detections": ocr_result.get("detections"),
    }
