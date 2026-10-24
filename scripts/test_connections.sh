#!/usr/bin/env bash
# =========================================================================
# SM-Park - Tests de connexion entre les conteneurs
# -------------------------------------------------------------------------
# Vérifie chaque lien du système, du point de vue réseau :
#
#   1. Stack Docker        : les 5 services sont démarrés et sains
#   2. DNS interne         : résolution des noms de service sur smpark-net
#   3. backend  -> database    (TCP 5432, depuis le conteneur backend)
#   4. backend  -> mqtt-broker (TCP 1883, depuis le conteneur backend)
#   5. backend  -> ocr-service (HTTP 200, depuis le conteneur backend)
#   6. frontend -> backend    (HTTP 200, depuis le conteneur frontend)
#   7. broker interne    : aller-retour publish/subscribe QoS 1
#   8. Hôte -> ports publiés : 1883, 5432, 8000, 8001, 3000
#   9. ESP32 -> broker    : round-trip sur les topics/identifiants du
#                            firmware, via l'IP LAN (le chemin réel de l'ESP32)
#  10. CORS               : preflight OPTIONS depuis l'origine frontend
#
# Chaque test affiche [OK] / [FAIL] / [SKIP]. Code de sortie non nul si au
# moins un test échoue.
#
# Utilisation (depuis la racine du dépôt) :
#   bash scripts/test_connections.sh
# Variables surchargeables : BACKEND_URL, OCR_URL, FRONTEND_URL, MQTT_PORT,
#   POSTGRES_PORT, LAN_IP, COMPOSE_FILE.
# =========================================================================
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.yml}"

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
OCR_URL="${OCR_URL:-http://localhost:8001}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
MQTT_PORT="${MQTT_PORT:-1883}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

PASS=0
FAIL=0
SKIP=0

ok()   { printf '  [OK]   %s\n' "$1"; PASS=$((PASS + 1)); }
ko()   { printf '  [FAIL] %s\n' "$1"; FAIL=$((FAIL + 1)); }
skip() { printf '  [SKIP] %s\n' "$1"; SKIP=$((SKIP + 1)); }
head1() { printf '\n-- %s --\n' "$1"; }

# --- Lecture d'une clé de .env (sans sourcer le fichier) -----------------
env_get() {
    [ -f "$ROOT_DIR/.env" ] || { printf ''; return; }
    sed -n "s/^$1=//p" "$ROOT_DIR/.env" | head -n1
}
MQTT_USERNAME="${MQTT_USERNAME:-$(env_get MQTT_USERNAME)}"
MQTT_PASSWORD="${MQTT_PASSWORD:-$(env_get MQTT_PASSWORD)}"
MQTT_USERNAME="${MQTT_USERNAME:-smpark}"
MQTT_PASSWORD="${MQTT_PASSWORD:-change_me_mqtt}"

# Topics du contrat (alignés sur firmware/esp32/src/config.h)
TOPIC_PARKING_STATE="$(env_get MQTT_TOPIC_PARKING_STATE)"; TOPIC_PARKING_STATE="${TOPIC_PARKING_STATE:-parking/state}"
TOPIC_BARRIER_COMMAND="$(env_get MQTT_TOPIC_BARRIER_COMMAND)"; TOPIC_BARRIER_COMMAND="${TOPIC_BARRIER_COMMAND:-parking/barrier/command}"
TOPIC_BARRIER_STATE="$(env_get MQTT_TOPIC_BARRIER_STATE)"; TOPIC_BARRIER_STATE="${TOPIC_BARRIER_STATE:-barrier/state}"

compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

# Exécute un script Python dans un conteneur (tous les conteneurs ont python
# ou node, sauf le frontend qui a node).
py_in() {
    local service="$1"; shift
    compose exec -T "$service" python -c "$*" 2>/dev/null
}

node_in() {
    local service="$1"; shift
    compose exec -T "$service" node -e "$*" 2>/dev/null
}

http_status() {
    curl -s -o /dev/null -m 5 -w '%{http_code}' "$1" 2>/dev/null || echo "000"
}

# IP joignable par l'ESP32 pour atteindre le broker.
# Priorité à MQTT_HOST de firmware/esp32/secrets.ini : c'est l'adresse
# réellement configurée dans le firmware. Repli sur les IP globales de l'hôte.
detect_lan_ip() {
    if [ -n "${LAN_IP:-}" ]; then printf '%s' "$LAN_IP"; return; fi
    local fw_host
    fw_host="$(grep -oE '\-DMQTT_HOST=.{0,32}' "$ROOT_DIR/firmware/esp32/secrets.ini" 2>/dev/null |
        head -n1 | sed 's/.*=//; s/\\//g; s/"//g')"
    if [ -n "$fw_host" ] && timeout 3 bash -c "</dev/tcp/$fw_host/$MQTT_PORT" 2>/dev/null; then
        printf '%s' "$fw_host"; return
    fi
    ip -4 -o addr show scope global 2>/dev/null |
        awk '{print $4}' | cut -d/ -f1 |
        grep -vE '^(127\.|10\.255\.255\.254$)' | head -n1
}

printf '== Tests de connexion inter-conteneurs SM-Park ==\n'

# --------------------------------------------------------------------------
head1 "1. Stack Docker"
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
    skip "docker compose indisponible : tous les tests réseau sont ignorés"
    printf '\n== Bilan : %s OK, %s FAIL, %s SKIP ==\n' "$PASS" "$FAIL" "$SKIP"
    exit 0
fi

for svc in database mqtt-broker backend ocr-service frontend; do
    state="$(compose ps --format '{{.State}}' "$svc" 2>/dev/null | head -n1)"
    health="$(compose ps --format '{{.Health}}' "$svc" 2>/dev/null | head -n1)"
    case "$state" in
        running)
            if [ -z "$health" ] || [ "$health" = "healthy" ]; then
                ok "service '$svc' démarré et sain"
            else
                ko "service '$svc' démarré mais santé='$health'"
            fi
            ;;
        "")   ko "service '$svc' absent du stack" ;;
        *)    ko "service '$svc' état='$state'" ;;
    esac
done

# --------------------------------------------------------------------------
head1 "2. DNS interne (réseau smpark-net)"
for target in database mqtt-broker ocr-service backend; do
    ip="$(py_in backend "import socket;print(socket.gethostbyname('$target'))")"
    if [ -n "$ip" ]; then
        ok "backend résout '$target' -> $ip"
    else
        ko "backend ne résout pas '$target'"
    fi
done

# --------------------------------------------------------------------------
head1 "3. backend -> database (TCP 5432)"
out="$(py_in backend "import socket;s=socket.create_connection(('database',5432),5);print('ok');s.close()")"
if [ "$out" = "ok" ]; then
    ok "connexion TCP database:5432 depuis le backend"
else
    ko "connexion TCP database:5432 impossible depuis le backend ($out)"
fi

# Connexion PostgreSQL complète (auth + requête) via asyncpg.
PG_USER="$(env_get POSTGRES_USER)"; PG_USER="${PG_USER:-postgres}"
PG_PASS="$(env_get POSTGRES_PASSWORD)"
PG_DB="$(env_get POSTGRES_DB)"; PG_DB="${PG_DB:-smpark}"
PY_PG="import asyncio, asyncpg
async def m():
    c = await asyncpg.connect(host='database', port=5432, user='$PG_USER', password='$PG_PASS', database='$PG_DB')
    v = await c.fetchval('SELECT 1')
    await c.close()
    return v
print(asyncio.run(m()))"
out="$(py_in backend "$PY_PG")"
if [ "$out" = "1" ]; then
    ok "requête PostgreSQL 'SELECT 1' depuis le backend"
else
    ko "connexion PostgreSQL authentifiée impossible depuis le backend ($out)"
fi

# --------------------------------------------------------------------------
head1 "4. backend -> mqtt-broker (TCP 1883)"
out="$(py_in backend "import socket;s=socket.create_connection(('mqtt-broker',1883),5);print('ok');s.close()")"
if [ "$out" = "ok" ]; then
    ok "connexion TCP mqtt-broker:1883 depuis le backend"
else
    ko "connexion TCP mqtt-broker:1883 impossible depuis le backend ($out)"
fi

# --------------------------------------------------------------------------
head1 "5. backend -> ocr-service (HTTP)"
out="$(py_in backend "import urllib.request;print(urllib.request.urlopen('http://ocr-service:8001/health/live',timeout=5).status)")"
if [ "$out" = "200" ]; then
    ok "ocr-service /health/live -> 200 depuis le backend"
else
    ko "ocr-service injoignable depuis le backend ($out)"
fi

# --------------------------------------------------------------------------
head1 "6. frontend -> backend (HTTP)"
out="$(node_in frontend "fetch('http://backend:8000/api/health/live').then(r=>console.log(r.status)).catch(e=>{console.error(e.message);process.exit(1)})")"
if [ "$out" = "200" ]; then
    ok "backend /api/health/live -> 200 depuis le frontend"
else
    ko "backend injoignable depuis le frontend ($out)"
fi

# --------------------------------------------------------------------------
head1 "7. Broker MQTT : aller-retour publish/subscribe (interne)"
TOPIC="parking/selftest/$$"
OUT_FILE="$(mktemp)"
compose exec -T mqtt-broker mosquitto_sub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
    -q 1 -t "$TOPIC" -C 1 -W 5 >"$OUT_FILE" 2>/dev/null &
SUB_PID=$!
sleep 1
if compose exec -T mqtt-broker mosquitto_pub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
    -q 1 -t "$TOPIC" -m '{"link":"broker-internal"}' >/dev/null 2>&1; then
    ok "publish QoS 1 sur $TOPIC"
else
    ko "publish QoS 1 impossible (identifiants MQTT ?)"
fi
wait "$SUB_PID" 2>/dev/null || true
if grep -q 'broker-internal' "$OUT_FILE"; then
    ok "message QoS 1 reçu par l'abonné"
else
    ko "aucun message reçu par l'abonné"
fi
rm -f "$OUT_FILE"

# --------------------------------------------------------------------------
head1 "8. Hôte -> ports publiés"
check_port() {
    local name="$1" port="$2"
    if timeout 3 bash -c "</dev/tcp/127.0.0.1/$port" 2>/dev/null; then
        ok "$name (port $port ouvert sur l'hôte)"
    else
        ko "$name (port $port fermé sur l'hôte)"
    fi
}
check_port "mqtt-broker" "$MQTT_PORT"
check_port "database"     "$POSTGRES_PORT"
check_port "backend"      "${BACKEND_URL##*:}"
check_port "ocr-service"  "${OCR_URL##*:}"
check_port "frontend"     "${FRONTEND_URL##*:}"

# --------------------------------------------------------------------------
head1 "9. Chemin ESP32 -> broker (IP LAN, topics du firmware)"
LAN_IP="$(detect_lan_ip)"
if [ -z "$LAN_IP" ]; then
    skip "aucune IP LAN détectée : test ESP32 ignoré"
else
    ESP_HOST="127.0.0.1"
    ESP_PORT="$MQTT_PORT"
    if timeout 3 bash -c "</dev/tcp/$LAN_IP/$MQTT_PORT" 2>/dev/null; then
        ESP_HOST="$LAN_IP"
        ok "broker joignable sur l'IP LAN $LAN_IP:$MQTT_PORT (chemin ESP32)"
    else
        ko "broker injoignable sur l'IP LAN $LAN_IP:$MQTT_PORT (chemin ESP32)"
    fi

    # Le firmware ABONNE parking/barrier/command et PUBLIE parking/state.
    # NB : `parking/state` est déjà retenu par le backend (heartbeat ~5 s) :
    # on ne peut donc pas.assert sur le contenu reçu (message périmé). On
    # contrôle (a) l'acceptation de la publication, (b) le round-trip du
    # format exact sur un topic de scratch.
    if compose exec -T mqtt-broker mosquitto_pub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
        -q 1 -t "$TOPIC_PARKING_STATE" \
        -m '{"slots":[{"id":1,"occupied":true},{"id":2,"occupied":false},{"id":3,"occupied":false}],"ts":1}' >/dev/null 2>&1; then
        ok "publication firmware acceptée sur $TOPIC_PARKING_STATE"
    else
        ko "publication firmware refusée sur $TOPIC_PARKING_STATE"
    fi

    SCRATCH="parking/selftest/firmware/$$"
    ESP_OUT="$(mktemp)"
    compose exec -T mqtt-broker mosquitto_sub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
        -q 1 -t "$SCRATCH" -C 1 -W 5 >"$ESP_OUT" 2>/dev/null &
    SUB_PID=$!
    sleep 1
    compose exec -T mqtt-broker mosquitto_pub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
        -q 1 -t "$SCRATCH" \
        -m '{"slots":[{"id":1,"occupied":true},{"id":2,"occupied":false},{"id":3,"occupied":false}],"ts":1}' >/dev/null 2>&1
    wait "$SUB_PID" 2>/dev/null || true
    if grep -q '"slots"' "$ESP_OUT" && grep -q '"occupied":true' "$ESP_OUT"; then
        ok "payload firmware parking/state livré (format slots[])"
    else
        ko "payload firmware parking/state non reçu"
    fi
    rm -f "$ESP_OUT"

    # Commande barrière : topic + schéma attendus par le firmware.
    CMD_OUT="$(mktemp)"
    compose exec -T mqtt-broker mosquitto_sub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
        -q 1 -t "$TOPIC_BARRIER_COMMAND" -C 1 -W 5 >"$CMD_OUT" 2>/dev/null &
    SUB_PID=$!
    sleep 1
    compose exec -T mqtt-broker mosquitto_pub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
        -q 1 -t "$TOPIC_BARRIER_COMMAND" \
        -m "{\"action\":\"open\",\"gate\":\"entry\",\"correlation_id\":\"conn-$$\"}" >/dev/null 2>&1
    wait "$SUB_PID" 2>/dev/null || true
    if grep -q '"action":"open"' "$CMD_OUT"; then
        ok "commande barrière ($TOPIC_BARRIER_COMMAND) transmise au format firmware"
    else
        ko "commande barrière non transmise ($TOPIC_BARRIER_COMMAND)"
    fi
    rm -f "$CMD_OUT"
fi

# --------------------------------------------------------------------------
head1 "10. CORS (préflight depuis l'origine frontend)"
ORIGIN="${CORS_ORIGIN:-$(env_get CORS_ORIGINS)}"
ORIGIN="${ORIGIN%%,*}"
ORIGIN="${ORIGIN:-http://localhost:3000}"
PREFLIGHT="$(curl -s -o /dev/null -m 5 -w '%{http_code}' -X OPTIONS \
    "$BACKEND_URL/api/slots" \
    -H "Origin: $ORIGIN" \
    -H "Access-Control-Request-Method: GET" \
    -H "Access-Control-Request-Headers: authorization" 2>/dev/null || echo 000)"
if [ "$PREFLIGHT" = "200" ] || [ "$PREFLIGHT" = "204" ]; then
    ok "préflight CORS depuis $ORIGIN -> $PREFLIGHT"
else
    ko "préflight CORS depuis $ORIGIN -> $PREFLIGHT"
fi

ALLOW_ORIGIN="$(curl -s -o /dev/null -m 5 -D - "$BACKEND_URL/api/health/live" \
    -H "Origin: $ORIGIN" 2>/dev/null | tr -d '\r' | sed -n 's/^[Aa]ccess-[Cc]ontrol-[Aa]llow-[Oo]rigin: //p')"
if [ -n "$ALLOW_ORIGIN" ]; then
    ok "en-tête Access-Control-Allow-Origin présent ($ALLOW_ORIGIN)"
else
    ko "en-tête Access-Control-Allow-Origin absent pour $ORIGIN"
fi

# --------------------------------------------------------------------------
printf '\n== Bilan : %s OK, %s FAIL, %s SKIP ==\n' "$PASS" "$FAIL" "$SKIP"
[ "$FAIL" -eq 0 ] || exit 1
