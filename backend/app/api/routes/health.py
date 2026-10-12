"""Routes de healthcheck : état de l'API, de la base et du broker MQTT."""

import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.mqtt import mqtt_service

logger = logging.getLogger("smpark.health")

router = APIRouter(tags=["health"])


@router.get("/health/live", summary="Liveness probe (le processus répond)")
async def liveness() -> dict:
    return {"status": "alive"}


@router.get("/health", summary="Healthcheck complet (DB + MQTT)")
async def health(response: Response, session: AsyncSession = Depends(get_session)) -> dict:
    db_up = False
    try:
        await session.execute(text("SELECT 1"))
        db_up = True
    except Exception as exc:  # noqa: BLE001 - on veut capturer toute erreur
        logger.error("Base de données injoignable : %s", exc)

    mqtt_up = mqtt_service.connected

    overall = db_up and mqtt_up
    if not overall:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if overall else "degraded",
        "services": {
            "database": "up" if db_up else "down",
            "mqtt": "up" if mqtt_up else "down",
        },
    }
