"""Routes de scan : capture webcam ou image envoyée, puis reconnaissance OCR."""

import logging

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.camera import CameraError, CameraService
from app.services.ocr import engine

logger = logging.getLogger("smpark.ocr.api")
settings = get_settings()

router = APIRouter(tags=["scan"])


# --- Schémas de réponse ---
class Detection(BaseModel):
    text: str
    confidence: float
    box: list[list[int]]


class ScanResult(BaseModel):
    plate: str | None
    confidence: float | None
    detections: list[Detection]
    source: str


def _run_ocr(image: np.ndarray, source: str) -> ScanResult:
    if not engine.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le moteur OCR est en cours de chargement.",
        )
    detections = engine.read(image)
    best = engine.read_best(image)
    return ScanResult(
        plate=best["text"] if best else None,
        confidence=best["confidence"] if best else None,
        detections=[Detection(**d) for d in detections],
        source=source,
    )


@router.post("/scan", response_model=ScanResult, summary="Capture webcam + OCR")
async def scan_from_camera() -> ScanResult:
    """Capture une image depuis la webcam puis applique l'OCR."""
    try:
        image = CameraService().capture()
    except CameraError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return _run_ocr(image, source="camera")


@router.post("/scan/upload", response_model=ScanResult, summary="OCR sur image envoyée")
async def scan_from_upload(file: UploadFile = File(...)) -> ScanResult:
    """Applique l'OCR à une image fournie (multipart/form-data)."""
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fichier vide.",
        )

    buffer = np.frombuffer(content, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image illisible ou format non supporté.",
        )

    return _run_ocr(image, source=f"upload:{file.filename}")


@router.get("/camera/preview", summary="Aperçu JPEG de la webcam")
async def camera_preview() -> Response:
    """Renvoie la dernière image capturée en JPEG (debug / intégration)."""
    try:
        image = CameraService().capture()
    except CameraError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    ok, encoded = cv2.imencode(".jpg", image)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Échec de l'encodage JPEG.",
        )
    return Response(content=encoded.tobytes(), media_type="image/jpeg")
