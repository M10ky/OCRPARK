"""Configuration centralisée du backend (lue depuis l'environnement)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres de l'application, surchargeables par variables d'environnement."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Général ---
    PROJECT_NAME: str = "SM-Park"
    PROJECT_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    TZ: str = "UTC"

    # --- API ---
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    SECRET_KEY: str = "change_me_super_secret_key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: str = "http://localhost:3000"

    # --- PostgreSQL ---
    DATABASE_URL: str = (
        "postgresql+asyncpg://smpark:smpark@database:5432/smpark"
    )

    # --- MQTT ---
    MQTT_HOST: str = "mqtt-broker"
    MQTT_PORT: int = 1883
    MQTT_USERNAME: str = "smpark"
    MQTT_PASSWORD: str = "smpark"
    MQTT_CLIENT_ID: str = "backend-smpark"
    MQTT_TOPIC_PARKING_STATE: str = "smpark/parking/state"
    MQTT_TOPIC_PARKING_EVENTS: str = "smpark/parking/events"
    MQTT_TOPIC_BARRIER_CMD: str = "smpark/barrier/command"
    MQTT_TOPIC_BARRIER_STATE: str = "smpark/barrier/state"

    @property
    def cors_origins(self) -> list[str]:
        """Liste des origines CORS autorisées à partir de la variable CSV."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Retourne l'instance unique (mise en cache) des paramètres."""
    return Settings()
