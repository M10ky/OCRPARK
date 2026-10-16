"""Client MQTT asynchrone (aiomqtt) avec reconnexion automatique.

Le backend publie/écoute les topics du système SM-Park. La connexion est
maintenue en tâche de fond ; l'état est exposé pour le healthcheck.
"""

import asyncio
import logging

import aiomqtt

from app.core.config import get_settings

logger = logging.getLogger("smpark.mqtt")
settings = get_settings()


class MQTTService:
    """Gère une connexion MQTT persistante et réactive aux erreurs."""

    RECONNECT_DELAY = 5

    @property
    def is_connected(self) -> bool:
        return self.connected

    def __init__(self) -> None:
        self.host = settings.MQTT_HOST
        self.port = settings.MQTT_PORT
        self.username = settings.MQTT_USERNAME
        self.password = settings.MQTT_PASSWORD
        self.client_id = settings.MQTT_CLIENT_ID
        self.subscribe_topics = [
            settings.MQTT_TOPIC_PARKING_STATE,
            settings.MQTT_TOPIC_PARKING_EVENTS,
            settings.MQTT_TOPIC_BARRIER_STATE,
        ]
        self.connected = False
        self._task: asyncio.Task | None = None
        self._client: aiomqtt.Client | None = None

    async def _listen(self) -> None:
        """Boucle principale : connexion, abonnement, écoute, reconnexion."""
        while True:
            try:
                async with aiomqtt.Client(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    identifier=self.client_id,
                ) as client:
                    self._client = client
                    self.connected = True
                    logger.info("Connecté au broker MQTT %s:%s", self.host, self.port)

                    for topic in self.subscribe_topics:
                        await client.subscribe(topic)
                    logger.info("Abonné aux topics : %s", ", ".join(self.subscribe_topics))

                    async for message in client.messages:
                        logger.debug(
                            "Message MQTT reçu [%s] : %s",
                            message.topic,
                            message.payload,
                        )
            except asyncio.CancelledError:
                self.connected = False
                logger.info("Arrêt de la boucle MQTT.")
                raise
            except (aiomqtt.MqttError, OSError) as exc:
                self.connected = False
                logger.warning(
                    "MQTT indisponible (%s). Nouvelle tentative dans %ss.",
                    exc,
                    self.RECONNECT_DELAY,
                )
                await asyncio.sleep(self.RECONNECT_DELAY)

    async def publish(self, topic: str, payload) -> bool:
        """Publie un message. Retourne True si la publication a été remise au
        client, False sinon (déconnecté / erreur) — jamais d'échec en silence."""
        import json

        if self._client is None or not self.connected:
            logger.warning("Publication MQTT ignorée (non connecté) : %s", topic)
            return False
        try:
            if isinstance(payload, dict):
                await self._client.publish(topic, json.dumps(payload))
            else:
                await self._client.publish(topic, str(payload))
            return True
        except Exception as exc:  # noqa: BLE001 — aiomqtt lève MqttError/OSError
            logger.warning("Échec de publication MQTT sur %s : %s", topic, exc)
            return False

    async def start(self) -> None:
        """Démarre la connexion MQTT en arrière-plan."""
        if self._task is None:
            self._task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        """Arrête proprement la tâche de connexion."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.connected = False


mqtt_client = MQTTService()


def is_connected() -> bool:
    return mqtt_client.connected


async def publish_json(topic: str, payload: dict | str) -> bool:
    import json

    if isinstance(payload, dict):
        return await mqtt_client.publish(topic, json.dumps(payload))
    return await mqtt_client.publish(topic, str(payload))

