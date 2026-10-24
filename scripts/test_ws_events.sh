#!/usr/bin/env bash
# =========================================================================
# SM-Park - Test du contrat WebSocket (snapshot / slots / barrier)
# -------------------------------------------------------------------------
# Crée un utilisateur jetable, récupère un JWT puis exécute le scénario
# WebSocket + MQTT complet DANS le conteneur backend (websockets + paho-mqtt
# y sont disponibles).
#
# Utilisation (depuis la racine du dépôt) :
#   bash scripts/test_ws_events.sh
# =========================================================================
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.yml}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"

printf '== Test du contrat WebSocket SM-Park ==\n'

if ! docker compose -f "$COMPOSE_FILE" version >/dev/null 2>&1; then
    echo "  [SKIP] docker compose indisponible"
    exit 0
fi

USER="ws_$(date +%s)_$$"
PASS="ws_pass_123"

reg_code="$(curl -s -o /dev/null -m 10 -w '%{http_code}' -X POST "$BACKEND_URL/api/auth/register" \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"$USER\",\"password\":\"$PASS\"}")"
if [ "$reg_code" != "200" ]; then
    echo "  [FAIL] inscription de l'utilisateur de test (HTTP $reg_code)"
    exit 1
fi
echo "  [OK]   utilisateur de test créé ($USER)"

TOKEN="$(curl -s -m 10 -X POST "$BACKEND_URL/api/auth/login" \
    -d "username=$USER&password=$PASS" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')"
if [ -z "$TOKEN" ]; then
    echo "  [FAIL] obtention du JWT"
    exit 1
fi
echo "  [OK]   JWT obtenu"

docker compose -f "$COMPOSE_FILE" exec -T backend \
    python - --token "$TOKEN" <"$SCRIPT_DIR/ws_events_check.py"
exit $?
