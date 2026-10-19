"""Fiabilisation de la commande barrière : attente d'ACK et timeout.

Après publication de `parking/barrier/command`, on attend un `barrier/state`
portant le même `correlation_id` (ACK, traité par `mqtt_handlers`). Passé le
délai `BARRIER_ACK_TIMEOUT_SECONDS`, la commande restée `pending` est marquée
`timeout` et l'événement est diffusé (voir `docs/mqtt-contract.md` §D.4).
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.barrier_command import (
    BARRIER_CMD_PENDING,
    BARRIER_CMD_TIMEOUT,
    BarrierCommand,
)
from app.services.ws_manager import manager

logger = logging.getLogger("smpark.barrier")
settings = get_settings()

# Références des tâches de timeout actives (évite le garbage-collect).
_tasks: set[asyncio.Task] = set()


async def _resolve_timeout(correlation_id, timeout: float) -> None:
    try:
        await asyncio.sleep(timeout)
    except asyncio.CancelledError:
        raise

    async with AsyncSessionLocal() as session:
        command = await session.get(BarrierCommand, correlation_id)
        if command is None or command.status != BARRIER_CMD_PENDING:
            return
        command.status = BARRIER_CMD_TIMEOUT
        gate = command.gate
        action = command.action
        await session.commit()

    logger.warning(
        "Commande barrière sans ACK après %.1fs (correlation_id=%s)", timeout, correlation_id
    )
    await manager.broadcast(
        {
            "type": "barrier",
            "payload": {
                "state": None,
                "gate": gate,
                "action": action,
                "correlation_id": str(correlation_id),
                "ack_status": BARRIER_CMD_TIMEOUT,
            },
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    )


def schedule_ack_timeout(correlation_id, timeout: float | None = None) -> None:
    """Planifie la détection de timeout d'ACK pour une commande publiée."""
    delay = settings.BARRIER_ACK_TIMEOUT_SECONDS if timeout is None else timeout
    task = asyncio.create_task(_resolve_timeout(correlation_id, delay))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
