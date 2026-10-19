"""Handlers métier des messages MQTT entrants.

Contrat de référence : `docs/mqtt-contract.md`. Chaque handler ouvre sa propre
session DB (jamais celle d'une requête HTTP) et diffuse les changements via le
WebSocket sous la forme stable `{"type", "payload", "ts"}`.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.barrier_command import (
    BARRIER_CMD_ACKNOWLEDGED,
    BARRIER_CMD_PENDING,
    BarrierCommand,
)
from app.models.parking_slot import ParkingSlot
from app.models.passage import Passage
from app.models.visit import VISIT_STATUS_CLOSED, VISIT_STATUS_INSIDE, Visit
from app.services.ocr_client import normalize_plate
from app.services.ws_manager import manager

logger = logging.getLogger("smpark.handlers")

# Dernier état barrière connu (heartbeat ou ACK), en mémoire process.
last_barrier_state: dict | None = None

# Fenêtre de rattachement d'un passage autorisé à une visite.
_PASSAGE_LINK_WINDOW = timedelta(seconds=120)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_uuid(value) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


async def _broadcast(event_type: str, payload: dict) -> None:
    await manager.broadcast(
        {"type": event_type, "payload": payload, "ts": _now().isoformat()}
    )


async def _slots_snapshot(session) -> dict:
    rows = (
        await session.execute(select(ParkingSlot).order_by(ParkingSlot.id))
    ).scalars().all()
    slots = [{"id": s.id, "occupied": bool(s.occupied)} for s in rows]
    occupied = sum(1 for s in slots if s["occupied"])
    return {
        "slots": slots,
        "total": len(slots),
        "occupied": occupied,
        "free": len(slots) - occupied,
    }


async def _latest_authorized_passage(
    session, now: datetime, plate: str | None = None
) -> Passage | None:
    """Dernier passage autorisé récent, éventuellement filtré par plaque."""
    stmt = select(Passage).where(
        Passage.allowed.is_(True), Passage.created_at >= now - _PASSAGE_LINK_WINDOW
    )
    if plate:
        stmt = stmt.where(Passage.plate == plate)
    stmt = stmt.order_by(Passage.created_at.desc()).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()


def _visit_dict(visit: Visit) -> dict:
    return {
        "id": str(visit.id),
        "plate": visit.plate,
        "entry_gate": visit.entry_gate,
        "exit_gate": visit.exit_gate,
        "status": visit.status,
        "entry_at": visit.entry_at.isoformat() if visit.entry_at else None,
        "exit_at": visit.exit_at.isoformat() if visit.exit_at else None,
    }


async def current_snapshot() -> dict:
    """État courant pour l'événement WebSocket `snapshot` (à la connexion)."""
    async with AsyncSessionLocal() as session:
        slots = await _slots_snapshot(session)
        rows = (
            await session.execute(
                select(Visit)
                .where(Visit.status == VISIT_STATUS_INSIDE)
                .order_by(Visit.entry_at)
            )
        ).scalars().all()
        visits = [_visit_dict(v) for v in rows]
    return {"slots": slots, "visits": visits, "barrier": last_barrier_state}


async def handle_parking_state(payload) -> None:
    """`parking/state` : met à jour l'occupation des places (idempotent par id)."""
    if not isinstance(payload, dict) or not isinstance(payload.get("slots"), list):
        logger.warning("parking/state ignoré : payload sans 'slots' (%r)", payload)
        return

    async with AsyncSessionLocal() as session:
        updated = 0
        for entry in payload["slots"]:
            if not isinstance(entry, dict):
                continue
            slot_id = entry.get("id")
            occupied = entry.get("occupied")
            if not isinstance(slot_id, int) or not isinstance(occupied, bool):
                continue
            slot = await session.get(ParkingSlot, slot_id)
            if slot is None:
                logger.warning("parking/state : place inconnue id=%s (ignorée)", slot_id)
                continue
            if slot.occupied != occupied:
                slot.occupied = occupied
                updated += 1
        if updated:
            await session.commit()
        snapshot = await _slots_snapshot(session)

    if updated:
        logger.info("parking/state : %d place(s) mise(s) à jour", updated)
        await _broadcast("slots", snapshot)


async def _open_visit(session, gate: str, plate: str | None, now: datetime) -> Visit | None:
    existing = (
        await session.execute(
            select(Visit)
            .where(Visit.status == VISIT_STATUS_INSIDE, Visit.entry_gate == gate)
            .order_by(Visit.entry_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.plate is None and plate:
            existing.plate = plate
            logger.info("Visite %s : plaque complétée (%s)", existing.id, plate)
            return existing
        logger.info("Événement entry dupliqué ignoré (visite %s en cours sur %s)", existing.id, gate)
        return None

    passage = await _latest_authorized_passage(session, now, plate=plate)
    visit = Visit(
        plate=plate or (passage.plate if passage else None),
        entry_gate=gate,
        entry_at=now,
        status=VISIT_STATUS_INSIDE,
        entry_passage_id=passage.id if passage else None,
    )
    session.add(visit)
    await session.flush()
    logger.info("Visite ouverte : id=%s gate=%s plate=%s", visit.id, gate, visit.plate)
    return visit


async def _close_visit(session, gate: str, now: datetime) -> Visit | None:
    visit = (
        await session.execute(
            select(Visit)
            .where(Visit.status == VISIT_STATUS_INSIDE)
            .order_by(Visit.entry_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if visit is None:
        logger.warning("Événement exit sans visite en cours (gate=%s) : ignoré", gate)
        return None

    visit.status = VISIT_STATUS_CLOSED
    visit.exit_gate = gate
    visit.exit_at = now
    passage = await _latest_authorized_passage(session, now, plate=visit.plate)
    if passage is not None:
        visit.exit_passage_id = passage.id
        if visit.plate is None:
            visit.plate = passage.plate
    logger.info("Visite fermée : id=%s gate=%s", visit.id, gate)
    return visit


async def handle_parking_event(payload) -> None:
    """`parking/events` : ouvre (`entry`) ou ferme (`exit`) une visite."""
    if not isinstance(payload, dict):
        logger.warning("parking/events ignoré : payload non objet (%r)", payload)
        return
    event_type = payload.get("type")
    if event_type not in ("entry", "exit"):
        logger.warning("parking/events ignoré : type inconnu %r", event_type)
        return
    gate = payload.get("gate") or event_type
    plate = normalize_plate(payload.get("plate"))
    now = _now()

    async with AsyncSessionLocal() as session:
        if event_type == "entry":
            visit = await _open_visit(session, gate, plate, now)
        else:
            visit = await _close_visit(session, gate, now)
        if visit is None:
            return
        await session.commit()
        await session.refresh(visit)
        data = _visit_dict(visit)

    await _broadcast("visit", data)


async def handle_barrier_state(payload) -> None:
    """`barrier/state` : ACK d'une commande (si `correlation_id`) ou heartbeat."""
    global last_barrier_state
    if not isinstance(payload, dict):
        logger.warning("barrier/state ignoré : payload non objet (%r)", payload)
        return

    state = payload.get("state")
    gate = payload.get("gate")
    reason = payload.get("reason")
    correlation_id = payload.get("correlation_id")
    ack_status = None

    if correlation_id:
        async with AsyncSessionLocal() as session:
            cmd = await session.get(BarrierCommand, _as_uuid(correlation_id))
            if cmd is None:
                logger.warning("barrier/state ACK : correlation_id inconnu %s", correlation_id)
            else:
                if cmd.status == BARRIER_CMD_PENDING:
                    cmd.status = BARRIER_CMD_ACKNOWLEDGED
                    cmd.acked_at = _now()
                    await session.commit()
                ack_status = cmd.status
                logger.info("ACK barrière reçu : correlation_id=%s", correlation_id)

    last_barrier_state = {
        "state": payload.get("state"),
        "gate": gate,
        "reason": payload.get("reason"),
        "correlation_id": payload.get("correlation_id"),
        "ack_status": ack_status,
        "ts": _now().isoformat(),
    }
    await _broadcast("barrier", last_barrier_state)
