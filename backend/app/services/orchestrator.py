"""Orchestrateur : détection→OCR→décision→commande barrière."""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.allowed_plate import AllowedPlate
from app.models.passage import Passage
from app.services.mqtt import mqtt_client
from app.services.ocr_client import normalize_plate
from app.services.ws_manager import manager

settings = get_settings()

VALID_GATES = ("entry", "exit")


class OrchestratorResult:
    def __init__(self, **data: Any) -> None:
        self.__dict__.update(data)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__


async def decide_and_act(
    session: AsyncSession,
    ocr_result: dict[str, Any],
    source: str,
    gate: str = "entry",
) -> dict[str, Any]:
    """Décide (plaque autorisée ?) et ordonne l'action barrière.

    Ordre volontaire : le `Passage` est créé et commité AVANT la publication
    MQTT — jamais de barrière ouverte sans trace en base. `correlation_id` est
    l'UUID du passage (unique par passage, contrairement à la plaque) pour
    associer l'acquittement de la barrière à la bonne commande.
    """
    if gate not in VALID_GATES:
        raise ValueError(f"gate invalide : {gate!r} (attendu {VALID_GATES})")

    passage_id = uuid.uuid4()

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
    correlation_id = str(passage_id)

    # 1) Trace en base, en premier.
    passage = Passage(
        id=passage_id,
        plate=normalized,
        recognized=recognized,
        confidence=float(confidence) if confidence is not None else None,
        allowed=allowed,
        source=source,
        action=action,
        barrier_command_sent=False,
        barrier_action=barrier_action,
        mqtt_topic=None,
        reason=reason,
        ocr_detections=ocr_result.get("detections"),
    )
    session.add(passage)
    await session.commit()
    await session.refresh(passage)

    # 2) Publication MQTT ensuite, avec retour de succès explicite.
    barrier_command_sent = False
    if allowed:
        cmd = {
            "action": "open",
            "gate": gate,
            "plate": normalized,
            "reason": reason,
            "source": source,
            "correlation_id": correlation_id,
        }
        barrier_command_sent = await mqtt_client.publish(settings.MQTT_TOPIC_BARRIER_COMMAND, cmd)
        if barrier_command_sent:
            passage.barrier_command_sent = True
            passage.mqtt_topic = settings.MQTT_TOPIC_BARRIER_COMMAND
            await session.commit()
            await session.refresh(passage)

    decision = {
        "id": correlation_id,
        "plate": normalized,
        "recognized": recognized,
        "confidence": float(confidence) if confidence is not None else None,
        "allowed": allowed,
        "action": action,
        "gate": gate,
        "barrier_command_sent": barrier_command_sent,
        "barrier_action": barrier_action,
        "reason": reason,
        "source": source,
        "correlation_id": correlation_id,
        "detections": ocr_result.get("detections"),
    }

    # 3) Événement temps réel (socle phase D).
    try:
        await manager.broadcast(
            {
                "type": "passage",
                "payload": decision,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception:  # noqa: BLE001 — un WebSocket défaillant ne doit pas casser la décision
        pass

    return decision
