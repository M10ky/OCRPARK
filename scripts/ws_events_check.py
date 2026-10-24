#!/usr/bin/env python3
"""Vérifie le contrat WebSocket de SM-Park de bout en bout.

Exécuté DANS le conteneur backend (il dispose de `websockets` et `paho-mqtt`) :

    docker compose exec -T backend python - < scripts/ws_events_check.py --token <JWT>

Scénario :
  1. connexion WS (`/ws/events?token=...`) et réception du `snapshot` ;
  2. publication MQTT sur `parking/state` (occupation inversée) -> événement
     `slots` attendu avec la nouvelle occupation ;
  3. publication MQTT sur `barrier/state` (ACK) -> événement `barrier` attendu.

Sortie : rapport texte, code de retour 0 si tout est conforme.
"""

import asyncio
import json
import os
import sys

import paho.mqtt.client as mqtt
import websockets

TOKEN = ""
for index, arg in enumerate(sys.argv):
    if arg == "--token" and index + 1 < len(sys.argv):
        TOKEN = sys.argv[index + 1]

if not TOKEN:
    print("usage: ws_events_check.py --token <JWT>")
    sys.exit(2)

MQTT_HOST = os.getenv("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USERNAME", "smpark")
MQTT_PASS = os.getenv("MQTT_PASSWORD", "")
TOPIC_STATE = os.getenv("MQTT_TOPIC_PARKING_STATE", "parking/state")
TOPIC_BARRIER = os.getenv("MQTT_TOPIC_BARRIER_STATE", "barrier/state")

WS_URL = f"ws://localhost:8000/ws/events?token={TOKEN}"

results = []


def check(name, condition, detail=""):
    results.append((name, bool(condition), detail))
    print(f"  [{'OK' if condition else 'FAIL'}]   {name}" + (f" — {detail}" if detail else ""))


def mqtt_publish(topic, payload):
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id="ws-events-check", protocol=mqtt.MQTTv311
    )
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.connect(MQTT_HOST, MQTT_PORT, 30)
    client.loop_start()
    info = client.publish(topic, json.dumps(payload), qos=1)
    info.wait_for_publish(timeout=10)
    client.loop_stop()
    client.disconnect()


async def wait_for_type(ws, wanted, timeout=15):
    """Consomme les événements jusqu'à trouver le type attendu."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    seen = []
    while loop.time() < deadline:
        remaining = deadline - loop.time()
        raw = await asyncio.wait_for(ws.recv(), timeout=max(remaining, 0.1))
        event = json.loads(raw)
        seen.append(event.get("type"))
        if event.get("type") == wanted:
            return event, seen
    return None, seen


async def main():
    async with websockets.connect(WS_URL) as ws:
        snapshot, seen = await wait_for_type(ws, "snapshot", timeout=15)
        check("snapshot reçu à la connexion", snapshot is not None, f"types vus : {seen}")
        if snapshot:
            payload = snapshot.get("payload", {})
            check(
                "snapshot contient l'occupation des places",
                isinstance(payload.get("slots"), dict),
                f"clés : {sorted(payload.keys())}",
            )

        # --- occupation des places -----------------------------------------
        target = {"slots": [{"id": 1, "occupied": True}, {"id": 2, "occupied": False},
                            {"id": 3, "occupied": False}], "ts": 1}
        mqtt_publish(TOPIC_STATE, target)
        slots_event, seen = await wait_for_type(ws, "slots", timeout=15)
        check("événement `slots` reçu après publication MQTT", slots_event is not None,
              f"types vus : {seen}")
        if slots_event:
            slots = slots_event.get("payload", {}).get("slots", [])
            first = next((s for s in slots if s.get("id") == 1), None)
            check("place 1 marquée occupée", first is not None and first.get("occupied") is True,
                  f"slot 1 = {first}")

        # --- barrière ------------------------------------------------------
        barrier_payload = {
            "state": "open",
            "gate": "entry",
            "reason": "ws-contract-check",
            "correlation_id": "ws-check-1",
            "ack_status": "acknowledged",
            "ts": "2026-01-01T00:00:00+00:00",
        }
        mqtt_publish(TOPIC_BARRIER, barrier_payload)
        barrier_event, seen = await wait_for_type(ws, "barrier", timeout=15)
        check("événement `barrier` reçu après publication MQTT", barrier_event is not None,
              f"types vus : {seen}")
        if barrier_event:
            state = barrier_event.get("payload", {})
            check("état de la barrière transmis",
                  state.get("state") == "open" and state.get("gate") == "entry",
                  f"state={state.get('state')} gate={state.get('gate')}")

    failures = [name for name, ok, _ in results if not ok]
    print(f"\n== Bilan : {len(results) - len(failures)} OK, {len(failures)} FAIL ==")
    return 1 if failures else 0


try:
    sys.exit(asyncio.run(main()))
except Exception as exc:  # noqa: BLE001
    print(f"  [FAIL] exception : {exc}")
    sys.exit(1)
