"""Route racine : informations générales sur l'API."""

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["général"])
settings = get_settings()


@router.get("/", summary="Informations sur l'API")
async def read_root() -> dict:
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
        "health": "/api/health",
    }
