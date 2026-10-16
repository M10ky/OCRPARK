"""Client HTTP pour le service OCR."""
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings

settings = get_settings()


class OCRClient:
    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = (base_url or settings.OCR_SERVICE_URL).rstrip("/")
        self.timeout = timeout

    async def upload(self, file_bytes: bytes, filename: str | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            files = {"file": (filename or "image.jpg", file_bytes, "application/octet-stream")}
            try:
                resp = await client.post(f"{self.base_url}/scan/upload", files=files)
            except httpx.RequestError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Échec de connexion au service OCR : {exc}",
                ) from exc
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=resp.json().get("detail") if resp.content else "Erreur OCR",
                )
            return resp.json()

    async def scan_camera(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(f"{self.base_url}/scan")
            except httpx.RequestError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Échec de connexion au service OCR : {exc}",
                ) from exc
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=resp.json().get("detail") if resp.content else "Erreur OCR",
                )
            return resp.json()


def normalize_plate(text: str | None) -> str | None:
    if not text:
        return None
    return " ".join(text.upper().split()).strip().replace(" ", "")
