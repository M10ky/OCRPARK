#!/usr/bin/env bash
# =========================================================================
# SM-Park - Smoke test Phase D (backend « live »)
# -------------------------------------------------------------------------
# Couvre :
#   1. parking/state  -> occupation des places mise à jour en base
#   2. parking/events -> ouverture/fermeture d'une visite cohérente
#   3. orchestration autorisée -> commande + ack (BarrierCommand ack/nolead)
#   4. parking plein -> refus à l'entrée
#   5. WebSocket : réception du snapshot puis d'un événement live
#
# Prérequis : stack lancée (docker compose up -d).
# La phase A reste couverte par scripts/smoke_test.sh (à lancer aussi).
#
# Utilisation (depuis la racine du dépôt) :
#   bash scripts/smoke_test_phase_d.sh
# =========================================================================
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.yml}"

PASS=0
FAIL=0
SKIP=0
OUT="$(mktemp)"
trap 'rm -f "$OUT"' EXIT

dc() { docker compose -f "$COMPOSE_FILE" "$@"; }

printf '== Smoke test SM-Park (phase D) ==\n\n'

if ! dc exec -T backend true >/dev/null 2>&1; then
    printf '  [SKIP] conteneur backend indisponible\n'
    printf '\n== Bilan : 0 OK, 0 FAIL, 1 SKIP ==\n'
    exit 0
fi

dc exec -T backend python -u - >"$OUT" 2>&1 <<'PY'
import asyncio
import json
import os
import uuid

from sqlalchemy import delete, select, update

from app.db.session import AsyncSessionLocal
from app.models import AllowedPlate, BarrierCommand, ParkingSlot, Passage, Visit
from app.services import mqtt as mqtt_mod
from app.services import mqtt_handlers, orchestrator
from app.services.orchestrator import decide_and_act

USER = os.getenv("MQTT_USERNAME", "smpark")
PWD = os.getenv("MQTT_PASSWORD", "")
PLATE = "D7PLATE"


def pub(topic, payload, retain=False):
    import paho.mqtt.client as mqtt
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="d7-" + os.urandom(3).hex())
    c.username_pw_set(USER, PWD)
    c.connect("mqtt-broker", 1883, 10)
    body = payload if isinstance(payload, str) else json.dumps(payload)
    c.publish(topic, body, qos=1, retain=retain)
    c.disconnect()


def report(cond, msg):
    print(("[OK]   " if cond else "[FAIL] ") + msg)


async def slot_value(slot_id):
    async with AsyncSessionLocal() as s:
        return (await s.execute(
            select(ParkingSlot.occupied).where(ParkingSlot.id == slot_id)
        )).scalar_one_or_none()


async def wait_slot(slot_id, expected, tries=40):
    for _ in range(tries):
        if await slot_value(slot_id) == expected:
            return True
        await asyncio.sleep(0.1)
    return False


async def wait_visit(plate, tries=40):
    for _ in range(tries):
        async with AsyncSessionLocal() as s:
            v = (await s.execute(
                select(Visit).where(Visit.plate == plate).order_by(Visit.entry_at.desc()).limit(1)
            )).scalar_one_or_none()
            if v is not None:
                return {"id": v.id, "status": v.status, "exit_gate": v.exit_gate}
        await asyncio.sleep(0.1)
    return None


async def cmd_status(cid):
    async with AsyncSessionLocal() as s:
        return (await s.execute(
            select(BarrierCommand.status).where(BarrierCommand.correlation_id == cid)
        )).scalar_one_or_none()


async def main():
    # --- 1. parking/state -> occupation --------------------------------
    pub("parking/state", {"slots": [{"id": 1, "occupied": False}]}, retain=True)
    await wait_slot(1, False)
    pub("parking/state", {"slots": [{"id": 1, "occupied": True}]}, retain=True)
    report(await wait_slot(1, True), "parking/state : place 1 -> occupée en base")
    pub("parking/state", {"slots": [{"id": 1, "occupied": False}]}, retain=True)
    report(await wait_slot(1, False), "parking/state : place 1 -> libre en base")

    # --- 2. parking/events -> visite -----------------------------------
    plate = "PD" + os.urandom(3).hex().upper()
    pub("parking/events", {"type": "entry", "gate": "entry", "plate": plate})
    v = await wait_visit(plate)
    report(v is not None and v["status"] == "inside",
           "parking/events entry : visite 'inside' ouverte (%s)" % plate)
    pub("parking/events", {"type": "exit", "gate": "exit"})
    closed = None
    for _ in range(40):
        async with AsyncSessionLocal() as s:
            row = (await s.execute(
                select(Visit).where(Visit.plate == plate).order_by(Visit.entry_at.desc()).limit(1)
            )).scalar_one_or_none()
            if row is not None and row.status == "closed":
                closed = {"status": row.status, "exit_gate": row.exit_gate}
                break
        await asyncio.sleep(0.1)
    report(closed is not None and closed["exit_gate"] == "exit",
           "parking/events exit : visite 'closed' (exit_gate=exit)")

    # --- 3. orchestration autorisée -> commande + ack ------------------
    async def fake_publish(topic, payload, qos=1, retain=False):
        return True
    mqtt_mod.mqtt_client.publish = fake_publish
    orchestrator.settings.BARRIER_ACK_TIMEOUT_SECONDS = 2.0

    async with AsyncSessionLocal() as s:
        await s.execute(update(ParkingSlot).values(occupied=False))
        if (await s.execute(select(AllowedPlate).where(AllowedPlate.plate == PLATE))).scalar_one_or_none() is None:
            s.add(AllowedPlate(plate=PLATE, active=True))
        await s.commit()
        r = await decide_and_act(s, {"best": {"text": PLATE, "confidence": 0.95}}, "test:d7", gate="entry")
    cid = uuid.UUID(r["id"])
    report(r["allowed"] and r["action"] == "open" and await cmd_status(cid) == "pending",
           "orchestration : autorisée + place libre -> open, commande pending")

    await mqtt_handlers.handle_barrier_state(
        {"state": "opening", "gate": "entry", "correlation_id": r["id"]}
    )
    report(await cmd_status(cid) == "acknowledged", "barrier/state : ACK -> commande acknowledged")

    # --- 4. parking plein -> refus -------------------------------------
    async with AsyncSessionLocal() as s:
        await s.execute(update(ParkingSlot).values(occupied=True))
        await s.commit()
        r2 = await decide_and_act(s, {"best": {"text": PLATE, "confidence": 0.95}}, "test:d7", gate="entry")
        await s.execute(update(ParkingSlot).values(occupied=False))
        await s.commit()
    report((not r2["allowed"]) and r2["reason"] == "Parking plein",
           "orchestration : parking plein -> refus (reason='Parking plein')")

    # --- 5. WebSocket --------------------------------------------------
    import websockets
    snap_ok = event_ok = False
    async with websockets.connect("ws://localhost:8000/ws/events", open_timeout=5) as ws:
        snap = json.loads(await asyncio.wait_for(ws.recv(), 5))
        snap_ok = snap.get("type") == "snapshot"
        pub("parking/state", {"slots": [{"id": 2, "occupied": True}]})
        try:
            while True:
                m = json.loads(await asyncio.wait_for(ws.recv(), 6))
                if m.get("type") == "slots":
                    event_ok = any(x["id"] == 2 and x["occupied"] for x in m["payload"]["slots"])
                    break
        except asyncio.TimeoutError:
            pass
    pub("parking/state", {"slots": [{"id": 2, "occupied": False}]})
    report(snap_ok, "websocket : snapshot reçu à la connexion")
    report(event_ok, "websocket : événement 'slots' live reçu (place 2)")

    # --- Nettoyage -----------------------------------------------------
    async with AsyncSessionLocal() as s:
        await s.execute(delete(BarrierCommand))
        await s.execute(delete(Visit))
        await s.execute(delete(Passage).where(Passage.source == "test:d7"))
        await s.execute(delete(AllowedPlate).where(AllowedPlate.plate == PLATE))
        await s.execute(update(ParkingSlot).values(occupied=False))
        await s.commit()
    pub("parking/state",
        {"slots": [{"id": 1, "occupied": False}, {"id": 2, "occupied": False}, {"id": 3, "occupied": False}]},
        retain=True)


asyncio.run(main())
PY
RC=$?
cat "$OUT"

PASS=$(grep -c '^\[OK\]' "$OUT")
FAIL=$(grep -c '^\[FAIL\]' "$OUT")
SKIP=$(grep -c '^\[SKIP\]' "$OUT")
if [ "$RC" -ne 0 ]; then
    printf '\n  [FAIL] exécution des tests Phase D (code %s)\n' "$RC"
    FAIL=$((FAIL + 1))
fi

printf '\n== Bilan Phase D : %s OK, %s FAIL, %s SKIP ==\n' "$PASS" "$FAIL" "$SKIP"
[ "$FAIL" -eq 0 ] || exit 1
