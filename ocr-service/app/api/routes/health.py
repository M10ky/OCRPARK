"""Routes de healthcheck du service OCR."""

from fastapi import APIRouter

from app.services.camera import CameraService
from app.services.ocr import engine

router = APIRouter(tags=["health"])


@router.get("/health/live", summary="Liveness probe")
async def liveness() -> dict:
    return {"status": "alive"}


@router.get("/health", summary="État du moteur OCR et de la caméra")
async def health() -> dict:
    camera_available = CameraService().is_available()
    return {
        "status": "ok" if engine.ready else "loading",
        "services": {
            "ocr": "ready" if engine.ready else "loading",
            "camera": "available" if camera_available else "unavailable",
        },
    }
