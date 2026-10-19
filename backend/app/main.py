"""Point d'entrée du service Backend SM-Park (FastAPI)."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    auth,
    barrier,
    health,
    orchestrate,
    passages,
    plates,
    root,
    slots,
    visits,
    ws,
)
from app.core.config import get_settings
from app.services.mqtt import mqtt_client
from app.db.session import engine
from app.models.base import Base
from app.models import (  # noqa
    allowed_plate,
    barrier_command,
    parking_slot,
    passage,
    user,
    visit,
)
from app.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("smpark.backend")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Démarrage de %s v%s", settings.PROJECT_NAME, settings.PROJECT_VERSION)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    asyncio.create_task(mqtt_client.start())
    try:
        await init_db.init_db()
    except Exception as exc:
        logger.warning("init_db failed: %s", exc)
    yield
    logger.info("Arrêt du service Backend.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="API + logique métier + WebSocket SM-Park",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(root.router)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(plates.router)
app.include_router(passages.router)
app.include_router(orchestrate.router)
app.include_router(slots.router)
app.include_router(visits.router)
app.include_router(barrier.router)
app.include_router(ws.router)
