#!/usr/bin/env bash
# =========================================================================
# SM-Park - Smoke test de stabilisation (phase A)
# -------------------------------------------------------------------------
# Couvre :
#   1. Health    : backend (/api/health/live, /api/health), OCR (/health),
#                  base de données et broker MQTT (lus via /api/health).
#   2. MQTT      : connexion TCP + aller-retour publish/subscribe QoS 1.
#   3. API       : inscription + login (JWT).
#   4. Orchestration : upload -> décision (OCR -> DB), retour JSON.
#   5. Barrière simulée : commande -> ACK corrélé sur barrier/state.
#
# Chaque test affiche [OK] / [FAIL] / [SKIP]. Code de sortie non nul dès
# qu'au moins un test est en échec.
#
# Utilisation (depuis la racine du dépôt) :
#   bash scripts/smoke_test.sh
# Variables surchargeables : BACKEND_URL, OCR_URL, FRONTEND_URL, MQTT_HOST,
#   MQTT_PORT, COMPOSE_FILE. Les identifiants MQTT sont lus dans .env.
# =========================================================================
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.yml}"

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
OCR_URL="${OCR_URL:-http://localhost:8001}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
MQTT_HOST="${MQTT_HOST:-localhost}"
MQTT_PORT="${MQTT_PORT:-1883}"

PASS=0
FAIL=0
SKIP=0
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

ok()   { printf '  [OK]   %s\n' "$1"; PASS=$((PASS + 1)); }
ko()   { printf '  [FAIL] %s\n' "$1"; FAIL=$((FAIL + 1)); }
skip() { printf '  [SKIP] %s\n' "$1"; SKIP=$((SKIP + 1)); }

# --- Récupération d'une clé depuis .env (sans sourcer le fichier) ----------
env_get() {
    [ -f "$ROOT_DIR/.env" ] || { printf ''; return; }
    sed -n "s/^$1=//p" "$ROOT_DIR/.env" | head -n1
}
MQTT_USERNAME="${MQTT_USERNAME:-$(env_get MQTT_USERNAME)}"
MQTT_PASSWORD="${MQTT_PASSWORD:-$(env_get MQTT_PASSWORD)}"
MQTT_USERNAME="${MQTT_USERNAME:-smpark}"
MQTT_PASSWORD="${MQTT_PASSWORD:-change_me_mqtt}"

# --- Helpers HTTP ---
http_get() {
    if command -v curl >/dev/null 2>&1; then
        curl -s -m 5 "$1" 2>/dev/null
    else
        python3 - "$1" <<'PY' 2>/dev/null
import sys, urllib.request
try:
    with urllib.request.urlopen(sys.argv[1], timeout=5) as r:
        sys.stdout.write(r.read().decode("utf-8", "replace"))
except Exception:
    pass
PY
    fi
}

http_status() {
    if command -v curl >/dev/null 2>&1; then
        # curl imprime déjà 000 en cas d'échec de connexion : ne pas doubler.
        curl -s -o /dev/null -m 5 -w '%{http_code}' "$1" 2>/dev/null
    else
        python3 - "$1" <<'PY' 2>/dev/null || echo "000"
import sys, urllib.request
try:
    with urllib.request.urlopen(sys.argv[1], timeout=5) as r:
        print(r.status)
except Exception:
    print("000")
PY
    fi
}

check_http() {
    local name="$1" url="$2" code
    code="$(http_status "$url")"
    [ -z "$code" ] && code="000"
    if [ "$code" = "200" ]; then ok "$name ($url -> 200)"; else ko "$name ($url -> HTTP $code)"; fi
}

mqtt_ready() {
    command -v docker >/dev/null 2>&1 && docker compose -f "$COMPOSE_FILE" version >/dev/null 2>&1
}

# Exécute une commande mosquitto dans le conteneur du broker.
mqtt_exec() {
    docker compose -f "$COMPOSE_FILE" exec -T mqtt-broker "$@"
}

# =======================================================================
printf '== Smoke test SM-Park (phase A) ==\n'

# --- 1. Health --------------------------------------------------------
printf '\n-- Health --\n'
check_http "backend (live)" "$BACKEND_URL/api/health/live"
# /health/live évite la sonde webcam (lente/bloquante sur /health sans caméra).
check_http "ocr-service (live)" "$OCR_URL/health/live"
check_http "frontend" "$FRONTEND_URL/"

health_body="$(http_get "$BACKEND_URL/api/health")"
if printf '%s' "$health_body" | grep -q '"database": *"up"'; then
    ok "database (via /api/health)"
else
    ko "database (via /api/health) -> $health_body"
fi
if printf '%s' "$health_body" | grep -q '"mqtt": *"up"'; then
    ok "mqtt (via /api/health)"
else
    ko "mqtt (via /api/health) -> $health_body"
fi

# --- 2. MQTT pub/sub --------------------------------------------------
printf '\n-- MQTT --\n'
if ! mqtt_ready; then
    echo "  [SKIP] docker compose indisponible"
    echo "  [SKIP] roundtrip publish/subscribe MQTT"
else
    TOPIC="parking/smoketest/$$"
    OUT="$(mktemp)"
    mqtt_exec mosquitto_sub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
        -q 1 -t "$TOPIC" -C 1 -W 5 >"$OUT" 2>/dev/null &
    SUB_PID=$!
    sleep 1
    if mqtt_exec mosquitto_pub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
        -q 1 -t "$TOPIC" -m '{"msg":"smoke"}'; then
        ok "publish QoS 1 ($TOPIC)"
    else
        ko "publish QoS 1 ($TOPIC)"
    fi
    wait "$SUB_PID" 2>/dev/null || true
    if grep -q 'smoke' "$OUT"; then
        ok "subscribe QoS 1 (message reçu)"
    else
        ko "subscribe QoS 1 (aucun message reçu)"
    fi
    rm -f "$OUT"
fi

# --- 3. API auth ------------------------------------------------------
printf '\n-- API auth --\n'
USER="smoke_$(date +%s)_$$"
USERPASS="smoke_pass_123"
if command -v curl >/dev/null 2>&1; then
    reg_code="$(curl -s -o /dev/null -m 5 -w '%{http_code}' -X POST "$BACKEND_URL/api/auth/register" \
        -H 'Content-Type: application/json' \
        -d "{\"username\":\"$USER\",\"password\":\"$USERPASS\"}")"
    if [ "$reg_code" = "200" ]; then ok "register public (200)"; else ko "register public (HTTP $reg_code)"; fi

    TOKEN="$(curl -s -m 5 -X POST "$BACKEND_URL/api/auth/login" \
        -d "username=$USER&password=$USERPASS" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')"
    if [ -n "$TOKEN" ]; then ok "login (token JWT obtenu)"; else ko "login (pas de token)"; fi
else
    echo "  [SKIP] curl absent : tests API non exécutés"
    TOKEN=""
fi

# --- 4. Orchestration upload -> décision ------------------------------
printf '\n-- Orchestration --\n'
if [ -n "${TOKEN:-}" ]; then
    IMG="$(mktemp --suffix=.png)"
    # PNG 2x2 RGB valide (base64), décodable par OpenCV.
    printf '%s' 'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP4z8AARAwQCgAf7gP9i18U1AAAAABJRU5ErkJggg==' | base64 -d >"$IMG"
    code="$(curl -s -o /tmp/smoke_orch.json -m 20 -w '%{http_code}' -X POST \
        "$BACKEND_URL/api/orchestrate/upload?gate=entry" \
        -H "Authorization: Bearer $TOKEN" -F "file=@$IMG;type=image/png")"
    if [ "$code" = "200" ]; then
        ok "orchestrate/upload (200)"
        if grep -q '"recognized"' /tmp/smoke_orch.json; then
            ok "décision renvoyée (champ recognized)"
        else
            ko "décision invalide -> $(cat /tmp/smoke_orch.json)"
        fi
    elif [ "$code" = "503" ]; then
        echo "  [SKIP] OCR indisponible/chargement (503)"
    else
        ko "orchestrate/upload (HTTP $code) -> $(cat /tmp/smoke_orch.json 2>/dev/null)"
    fi
    rm -f "$IMG" /tmp/smoke_orch.json
else
    echo "  [SKIP] orchestration : pas de token"
fi

# --- 5. Commande barrière simulée -> ACK corrélé ----------------------
printf '\n-- Barrière simulée --\n'
if mqtt_ready; then
    CID="smoke-$$"
    ACK="$(mktemp)"
    SIM_LOG="$(mktemp)"
    # Nettoie d'éventuels simulateurs restés d'un run précédent.
    mqtt_exec pkill -f "mosquitto_sub -h localhost" 2>/dev/null || true
    # Purge l'état retenu pour ne pas recevoir un ACK périmé.
    mqtt_exec mosquitto_pub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
        -q 1 -r -n -t barrier/state 2>/dev/null || true
    docker compose -f "$COMPOSE_FILE" exec -T mqtt-broker sh -s <"$SCRIPT_DIR/barrier_sim.sh" >"$SIM_LOG" 2>&1 &
    SIM_PID=$!
    sleep 2
    # Capture plusieurs états et cherche celui portant notre correlation_id.
    mqtt_exec mosquitto_sub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
        -q 1 -t barrier/state -C 10 -W 6 >"$ACK" 2>/dev/null &
    SUB_PID=$!
    sleep 1
    mqtt_exec mosquitto_pub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
        -q 1 -t parking/barrier/command \
        -m "{\"action\":\"open\",\"gate\":\"entry\",\"correlation_id\":\"$CID\"}"
    wait "$SUB_PID" 2>/dev/null || true
    if grep -q "\"correlation_id\":\"$CID\"" "$ACK"; then
        ok "ACK corrélé reçu sur barrier/state (correlation_id=$CID)"
    else
        ko "ACK corrélé absent -> $(tr '\n' ' ' < "$ACK")"
    fi
    kill "$SIM_PID" 2>/dev/null || true
    mqtt_exec pkill -f "mosquitto_sub -h localhost" 2>/dev/null || true
    rm -f "$ACK" "$SIM_LOG"
else
    echo "  [SKIP] barrière simulée (docker compose indisponible)"
fi

# --- Bilan ------------------------------------------------------------
printf '\n== Bilan : %s OK, %s FAIL, %s SKIP ==\n' "$PASS" "$FAIL" "$SKIP"
[ "$FAIL" -eq 0 ] || exit 1
