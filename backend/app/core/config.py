"""Configuration centralisée du service Backend."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres du backend, surchargeables par variables d'environnement."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "SM-Park"
    PROJECT_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"

    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000"

    # Base de données
    DATABASE_URL: str = "postgresql+asyncpg://smpark:smpark@database:5432/smpark"

    # MQTT
    MQTT_HOST: str = "mqtt-broker"
    MQTT_PORT: int = 1883
    MQTT_USERNAME: str = "smpark"
    MQTT_PASSWORD: str = ""
    MQTT_CLIENT_ID: str = "smpark-backend"
    MQTT_KEEPALIVE: int = 60
    MQTT_TOPIC_PARKING_STATE: str = "parking/state"
    MQTT_TOPIC_PARKING_EVENTS: str = "parking/events"
    MQTT_TOPIC_BARRIER_STATE: str = "barrier/state"
    MQTT_TOPIC_BARRIER_COMMAND: str = "parking/barrier/command"

    # Service OCR
    OCR_SERVICE_URL: str = "http://ocr-service:8001"

    # Authentification JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
