#!/bin/sh
# =========================================================================
# SM-Park - Simulateur de barrière + capteurs MQTT (test phase A/7 SANS ESP32)
# -------------------------------------------------------------------------
# Ce script joue le rôle du firmware ESP32 :
#   - s'abonne à parking/barrier/command ;
#   - publie la séquence d'états sur barrier/state (retain, QoS 1) en écho
#     du correlation_id reçu (ACK) ;
#   - publie parking/events (entry/exit) et parking/state (occupation, retain).
# Contrat de référence : docs/mqtt-contract.md.
#
# Utilisation :
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
EVENTS_TOPIC="${MQTT_TOPIC_PARKING_EVENTS:-parking/events}"
PARKING_TOPIC="${MQTT_TOPIC_PARKING_STATE:-parking/state}"

# État local de la place 1 (simule un capteur d'occupation).
SLOT1_OCCUPIED="false"

# Extrait la valeur chaîne d'une clé JSON simple : extract "$payload" gate
extract() {
    printf '%s' "$1" | sed -n 's/.*"'"$2"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p'
}

# publish <topic> <payload> [retain]
publish() {
    _topic="$1"
    _msg="$2"
    _retain="${3:-false}"
    if [ "$_retain" = "true" ]; then
        mosquitto_pub -h "$HOST" -p "$PORT" -u "$USER_NAME" -P "$USER_PASS" \
            -q 1 -r -t "$_topic" -m "$_msg"
    else
        mosquitto_pub -h "$HOST" -p "$PORT" -u "$USER_NAME" -P "$USER_PASS" \
            -q 1 -t "$_topic" -m "$_msg"
    fi
}

# barrier/state [state] [reason] [correlation_id]
publish_state() {
    _state="$1"
    _reason="${2:-}"
    _cid="${3:-}"
    _msg="{\"state\":\"${_state}\",\"gate\":\"${GATE}\""
    [ -n "$_reason" ] && _msg="$_msg,\"reason\":\"${_reason}\""
    [ -n "$_cid" ] && _msg="$_msg,\"correlation_id\":\"${_cid}\""
    _msg="$_msg}"
    publish "$STATE_TOPIC" "$_msg" true
}

# Simule un cycle de capteurs : événement + occupation.
simulate_sensor_cycle() {
    _type="$1"
    if [ "$_type" = "entry" ]; then
        SLOT1_OCCUPIED="true"
    else
        SLOT1_OCCUPIED="false"
    fi
    publish "$EVENTS_TOPIC" \
        "{\"type\":\"${_type}\",\"gate\":\"${GATE}\",\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
    publish "$PARKING_TOPIC" \
        "{\"slots\":[{\"id\":1,\"occupied\":${SLOT1_OCCUPIED}}]}" true
}

GATE="entry"

# État initial d'occupation (retain) : 1 place libre.
publish "$PARKING_TOPIC" '{"slots":[{"id":1,"occupied":false}]}' true

echo "[sim] Barrière simulée en écoute sur '$CMD_TOPIC'"
echo "[sim] États sur '$STATE_TOPIC' (retain) ; capteurs sur '$EVENTS_TOPIC' / '$PARKING_TOPIC'"

mosquitto_sub -h "$HOST" -p "$PORT" -u "$USER_NAME" -P "$USER_PASS" \
    -q 1 -t "$CMD_TOPIC" -v |
while read -r _topic payload; do
    echo "[sim] Commande reçue : $payload"

    GATE="$(extract "$payload" gate)"
    [ -z "$GATE" ] && GATE="entry"
    CID="$(extract "$payload" correlation_id)"

    case "$payload" in
        *'"action":"open"'* | *'"action": "open"'*)
            simulate_sensor_cycle "$([ "$GATE" = "exit" ] && echo exit || echo entry)"
            # ACK : le premier état porte le correlation_id, les suivants non.
            publish_state opening "command" "$CID"
            sleep 0.5
            publish_state open
            sleep 0.5
            publish_state closing
            sleep 0.5
            publish_state closed
            ;;
        *'"action":"close"'* | *'"action": "close"'*)
            publish_state closing "command" "$CID"
            sleep 0.5
            publish_state closed
            ;;
        *)
            # ⚠️ Une commande invalide ne doit JAMAIS produire d'ACK : le
            # correlation_id n'est PAS renvoyé (le backend doit voir un
            # timeout, pas un faux succès). Voir l'audit C.1, F-07.
            publish_state idle "unknown_action"
            ;;
    esac
done
