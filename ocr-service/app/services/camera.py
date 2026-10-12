"""Capture d'images depuis une webcam via OpenCV.

La webcam est ouverte à la demande puis relâchée, afin de rester robuste sur
des environnements où le périphérique vidéo est partagé ou instable (WSL2).
"""

import logging

import cv2
import numpy as np

from app.core.config import get_settings

logger = logging.getLogger("smpark.ocr.camera")
settings = get_settings()


class CameraError(RuntimeError):
    """Erreur de capture (périphérique absent, occupé, etc.)."""


class CameraService:
    def __init__(self, index: int | None = None) -> None:
        self.index = settings.OCR_CAMERA_INDEX if index is None else index

    def is_available(self) -> bool:
        """Indique si au moins une image peut être lue depuis le périphérique."""
        try:
            self.capture()
            return True
        except CameraError:
            return False

    def capture(self) -> np.ndarray:
        """Ouvre la webcam, lit une image BGR et relâche le périphérique."""
        capture = cv2.VideoCapture(self.index)
        if not capture.isOpened():
            raise CameraError(
                f"Impossible d'ouvrir la caméra (index={self.index}). "
                "Vérifiez le passerelle /dev/video0 et les permissions."
            )

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, settings.OCR_CAMERA_WIDTH)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.OCR_CAMERA_HEIGHT)

        try:
            # Quelques lectures pour laisser la caméra s'initialiser (auto-expo).
            frame = None
            for _ in range(5):
                ok, frame = capture.read()
                if not ok:
                    frame = None
        finally:
            capture.release()

        if frame is None:
            raise CameraError("La caméra est ouverte mais aucune image n'a pu être lue.")

        logger.info("Image capturée depuis la caméra %s (%s)", self.index, frame.shape)
        return frame
