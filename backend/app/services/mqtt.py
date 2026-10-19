"""Client MQTT asynchrone (aiomqtt) avec reconnexion automatique.

Le backend publie/écoute les topics du système SM-Park. La connexion est
maintenue en tâche de fond ; l'état est exposé pour le healthcheck.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

import aiomqtt

from app.core.config import get_settings
from app.services import mqtt_handlers
from app.services.ws_manager import manager

logger = logging.getLogger("smpark.mqtt")
settings = get_settings()


def _decode_payload(payload) -> object:
    """Décode un payload MQTT brut : JSON si possible, sinon texte."""
    if isinstance(payload, (bytes, bytearray)):
        raw: str = payload.decode("utf-8", errors="replace")
    else:
        raw = str(payload)
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw


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

                    # QoS 1 (au moins une fois) : voir docs/mqtt-contract.md §C.
                    for topic in self.subscribe_topics:
                        await client.subscribe(topic, qos=1)
                    logger.info("Abonné aux topics (QoS 1) : %s", ", ".join(self.subscribe_topics))

                    async for message in client.messages:
                        # Routage métier puis relais éventuel vers les WebSockets.
                        # Un payload invalide ne doit jamais casser la boucle de
                        # reconnexion.
                        try:
                            await self._dispatch(str(message.topic), message.payload)
                        except Exception as exc:  # noqa: BLE001 — la boucle doit survivre
                            logger.warning("Message MQTT ignoré (traitement échoué) : %s", exc)
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

    async def _dispatch(self, topic: str, payload) -> None:
        """Route un message entrant vers le handler métier du contrat.

        Les topics du contrat (`docs/mqtt-contract.md` §C) sont traités par
        `mqtt_handlers` ; tout autre topic est relayé brut en fallback (`mqtt`).
        """
        decoded = _decode_payload(payload)
        if topic == settings.MQTT_TOPIC_PARKING_STATE:
            await mqtt_handlers.handle_parking_state(decoded)
        elif topic == settings.MQTT_TOPIC_PARKING_EVENTS:
            await mqtt_handlers.handle_parking_event(decoded)
        elif topic == settings.MQTT_TOPIC_BARRIER_STATE:
            await mqtt_handlers.handle_barrier_state(decoded)
        else:
            logger.debug("Message MQTT non routé [%s] : %s", topic, decoded)
            await manager.broadcast(
                {
                    "type": "mqtt",
                    "topic": topic,
                    "payload": decoded,
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
            )

    async def publish(
        self, topic: str, payload, qos: int = 1, retain: bool = False
    ) -> bool:
        """Publie un message. QoS 1 et retain=false par défaut, conformes au
        contrat MQTT (docs/mqtt-contract.md §C). Retourne True si la publication
        a été remise au client, False sinon (déconnecté / erreur) — jamais
        d'échec en silence."""
        if self._client is None or not self.connected:
            logger.warning("Publication MQTT ignorée (non connecté) : %s", topic)
            return False
        try:
            body = json.dumps(payload) if isinstance(payload, dict) else str(payload)
            await self._client.publish(topic, body, qos=qos, retain=retain)
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

