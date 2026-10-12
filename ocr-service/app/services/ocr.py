"""Enveloppe EasyOCR pour la reconnaissance de plaques d'immatriculation."""

import logging

import easyocr
import numpy as np

from app.core.config import get_settings

logger = logging.getLogger("smpark.ocr.engine")
settings = get_settings()


class OCREngine:
    """Charge le modèle EasyOCR une seule fois et expose des lectures."""

    def __init__(self) -> None:
        self.languages = settings.languages
        self.allowlist = settings.OCR_ALLOWLIST
        self.confidence_threshold = settings.OCR_CONFIDENCE_THRESHOLD
        self._reader: easyocr.Reader | None = None

    def load(self) -> None:
        """Charge les modèles EasyOCR (opération bloquante, à lancer au démarrage)."""
        if self._reader is None:
            logger.info("Chargement des modèles EasyOCR (langues=%s)...", self.languages)
            self._reader = easyocr.Reader(self.languages, gpu=False, verbose=False)
            logger.info("Modèles EasyOCR chargés.")

    @property
    def ready(self) -> bool:
        return self._reader is not None

    @staticmethod
    def _clean_text(text: str) -> str:
        return " ".join(text.upper().split()).strip()

    def read(self, image: np.ndarray) -> list[dict]:
        """Retourne la liste des textes détectés (texte, confiance, boîte)."""
        if self._reader is None:
            raise RuntimeError("Le moteur OCR n'est pas encore chargé.")

        raw = self._reader.readtext(
            image,
            detail=1,
            paragraph=False,
            allowlist=self.allowlist,
        )

        detections: list[dict] = []
        for box, text, confidence in raw:
            cleaned = self._clean_text(text)
            if not cleaned:
                continue
            detections.append(
                {
                    "text": cleaned,
                    "confidence": round(float(confidence), 4),
                    "box": [[int(px), int(py)] for px, py in box],
                }
            )

        detections.sort(key=lambda d: d["confidence"], reverse=True)
        return detections

    def read_best(self, image: np.ndarray) -> dict | None:
        """Retourne la détection la plus probable d'être une plaque."""
        # On privilégie une confiance élevée et un contenu alphanumérique long.
        candidates = [
            d for d in self.read(image)
            if d["confidence"] >= self.confidence_threshold
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda d: d["confidence"] * len(d["text"]))


engine = OCREngine()
