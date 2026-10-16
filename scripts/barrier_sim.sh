#!/bin/sh
# =========================================================================
# SM-Park - Simulateur de barrière MQTT (test Phase 7 SANS ESP32)
# -------------------------------------------------------------------------
# Ce script joue le rôle du firmware ESP32 : il s'abonne à la commande
# barrière et publie la séquence d'états correspondante.
#
# Utilisation (voir docs/tests/phase-7-tests-firmware.md) :
#   docker compose exec -T mqtt-broker sh -s < scripts/barrier_sim.sh
#
# Les paramètres peuvent être surchargés par variables d'environnement.
# =========================================================================
set -u

HOST="${MQTT_HOST:-localhost}"
PORT="${MQTT_PORT:-1883}"
USER_NAME="${MQTT_USERNAME:-smpark}"
USER_PASS="${MQTT_PASSWORD:-change_me_mqtt}"
CMD_TOPIC="${MQTT_TOPIC_BARRIER_COMMAND:-parking/barrier/command}"
STATE_TOPIC="${MQTT_TOPIC_BARRIER_STATE:-barrier/state}"

publish() {
    mosquitto_pub -h "$HOST" -p "$PORT" -u "$USER_NAME" -P "$USER_PASS" \
        -t "$STATE_TOPIC" -m "$1"
}

echo "[sim] Barrière simulée en écoute sur '$CMD_TOPIC'"
echo "[sim] Publication des états sur '$STATE_TOPIC' (Ctrl+C pour quitter)"

mosquitto_sub -h "$HOST" -p "$PORT" -u "$USER_NAME" -P "$USER_PASS" \
    -t "$CMD_TOPIC" -v |
while read -r _topic payload; do
    echo "[sim] Commande reçue : $payload"
    case "$payload" in
        *'"action":"open"'* | *'"action": "open"'*)
            for state in opening open closing closed; do
                publish "{\"state\":\"${state}\"}"
                sleep 0.5
            done
            ;;
        *'"action":"close"'* | *'"action": "close"'*)
            for state in closing closed; do
                publish "{\"state\":\"${state}\"}"
                sleep 0.5
            done
            ;;
        *)
            publish '{"state":"idle","reason":"unknown_action"}'
            ;;
    esac
done
