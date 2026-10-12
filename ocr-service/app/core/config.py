"""Configuration centralisée du service OCR."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres du service OCR, surchargeables par variables d'environnement."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "SM-Park OCR"
    PROJECT_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"

    OCR_HOST: str = "0.0.0.0"
    OCR_PORT: int = 8001
    OCR_CAMERA_INDEX: int = 0
    OCR_CAMERA_WIDTH: int = 1280
    OCR_CAMERA_HEIGHT: int = 720
    OCR_LANGUAGES: str = "en"
    OCR_CONFIDENCE_THRESHOLD: float = 0.5
    OCR_ALLOWLIST: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- "

    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def languages(self) -> list[str]:
        return [lang.strip() for lang in self.OCR_LANGUAGES.split(",") if lang.strip()]

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
