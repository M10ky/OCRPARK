"""Point d'entrée de l'API SM-Park (FastAPI)."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, root
from app.core.config import get_settings
from app.services.mqtt import mqtt_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("smpark")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Démarrage / arrêt des ressources partagées."""
    logger.info("Démarrage de %s v%s (%s)", settings.PROJECT_NAME, settings.PROJECT_VERSION, settings.ENVIRONMENT)
    await mqtt_service.start()
    yield
    await mqtt_service.stop()
    logger.info("Arrêt de l'API SM-Park.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="API du système de parking intelligent SM-Park.",
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
app.include_router(health.router, prefix="/api")
