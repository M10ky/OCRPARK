"""Point d'entrée du service OCR SM-Park (FastAPI)."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, scan
from app.core.config import get_settings
from app.services.ocr import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("smpark.ocr")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Démarrage de %s v%s", settings.PROJECT_NAME, settings.PROJECT_VERSION)
    # Le chargement EasyOCR est bloquant : on l'exécute hors de la boucle asyncio.
    await asyncio.to_thread(engine.load)
    yield
    logger.info("Arrêt du service OCR.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="Service de capture webcam et de reconnaissance de plaques (EasyOCR + OpenCV).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(scan.router)
