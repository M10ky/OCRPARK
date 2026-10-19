# Phase D — Tests backend « live »

Tests reproductibles de la Phase D (consommation MQTT, occupation, visites,
orchestration enrichie, WebSocket, API). Contrat de référence :
`docs/mqtt-contract.md` et `docs/websocket-contract.md`.

## Prérequis

```bash
docker compose up -d --build      # stack complète
```

## Lancement automatique (recommandé)

```bash
bash scripts/smoke_test_phase_d.sh   # attendu : 9 OK, 0 FAIL, 0 SKIP
bash scripts/smoke_test.sh           # phase A toujours verte : 12 OK, 0 FAIL
```

Le script Phase D crée puis nettoie ses données (visites, passages, commandes,
plaque `D7PLATE`, occupation remise à zéro).

## Détail des tests

Les identifiants MQTT sont lus dans `.env` (`MQTT_USERNAME`, `MQTT_PASSWORD`).
Exemples via le conteneur broker.

### 1. `parking/state` → occupation en base

```bash
docker compose exec -T mqtt-broker sh -c \
  'mosquitto_pub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
   -q 1 -r -t parking/state -m "{\"slots\":[{\"id\":1,\"occupied\":true}]}"'
docker compose exec -T database psql -U smpark -d smpark \
  -c "SELECT id, occupied FROM parking_slots WHERE id=1;"
```
**Attendu** : `occupied = t` (mise à jour **idempotente** par `id` ; un id inconnu
est ignoré avec un warning). Un événement WS `slots` est diffusé (voir test 5).

### 2. `parking/events` → visite cohérente

```bash
# Entrée
docker compose exec -T mqtt-broker sh -c \
  'mosquitto_pub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
   -q 1 -t parking/events -m "{\"type\":\"entry\",\"gate\":\"entry\",\"plate\":\"AB123CD\"}"'
# Sortie
docker compose exec -T mqtt-broker sh -c \
  'mosquitto_pub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
   -q 1 -t parking/events -m "{\"type\":\"exit\",\"gate\":\"exit\"}"'
docker compose exec -T database psql -U smpark -d smpark \
  -c "SELECT plate, entry_gate, exit_gate, status FROM visits ORDER BY entry_at DESC LIMIT 1;"
```
**Attendu** : `entry` ouvre une visite `inside` ; `exit` la ferme
(`status=closed`, `exit_gate=exit`). Un `entry` dupliqué (même portail) est ignoré.

### 3. Orchestration autorisée → commande + ACK

Via l'API (OCR réel) :
```bash
curl -s -X POST "http://localhost:8000/api/orchestrate/upload?gate=entry" \
  -H "Authorization: Bearer $TOKEN" -F "file=@photo_plaque.png"
```
Ou vérification déterministe (exécutée par `scripts/smoke_test_phase_d.sh`) :
plaque `D7PLATE` autorisée + place libre → décision `open`, `BarrierCommand`
`pending`, puis ACK `barrier/state` → `acknowledged`.
**Attendu** : commande `parking/barrier/command` avec `correlation_id` = id du
passage ; à l'ACK, la commande passe `acknowledged` (colonne `acked_at` non nulle).
Sans ACK sous `BARRIER_ACK_TIMEOUT_SECONDS` (défaut 5 s) → `timeout`.

### 4. Parking plein → refus à l'entrée

Toutes les places occupées, plaque autorisée, `gate=entry` :
**Attendu** : `allowed=false`, `reason="Parking plein"`, aucune commande publiée.
À `gate=exit`, la capacité n'est **pas** appliquée (la sortie n'est jamais bloquée).

### 5. WebSocket live

```bash
docker compose exec -T backend python -u - <<'PY'
import asyncio, json, os, websockets, paho.mqtt.client as mqtt
U=os.getenv("MQTT_USERNAME"); P=os.getenv("MQTT_PASSWORD")
async def main():
    async with websockets.connect("ws://localhost:8000/ws/events") as ws:
        print("snapshot:", json.loads(await asyncio.wait_for(ws.recv(), 5))["type"])
        c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ws-doc")
        c.username_pw_set(U,P); c.connect("mqtt-broker",1883,10)
        c.publish("parking/state", json.dumps({"slots":[{"id":1,"occupied":True}]}), qos=1); c.disconnect()
        print("event:", json.loads(await asyncio.wait_for(ws.recv(), 6))["type"])
asyncio.run(main())
PY
```
**Attendu** : `snapshot` à la connexion, puis `slots` à chaque changement.
Définitions : `docs/websocket-contract.md`.

### 6. Non-régression Phase A

```bash
bash scripts/smoke_test.sh
```
**Attendu** : `12 OK, 0 FAIL, 0 SKIP` (health, MQTT pub/sub QoS 1, auth,
orchestration, ACK barrière simulée).

## Résultats observés (validation Phase D)

| Bloc | Résultat |
|---|---|
| `scripts/smoke_test_phase_d.sh` | **9 OK, 0 FAIL, 0 SKIP** |
| `scripts/smoke_test.sh` | **12 OK, 0 FAIL, 0 SKIP** |
| `GET /api/slots`, `/api/visits`, `/api/visits/current`, `/api/barrier/state` | 200 (401 sans token) |

## Nettoyage manuel (si tests lancés à la main)

```bash
docker compose exec -T database psql -U smpark -d smpark -c \
 "DELETE FROM barrier_commands; DELETE FROM visits; \
  DELETE FROM passages WHERE source LIKE 'test:%' OR source LIKE 'orchestrator:%'; \
  UPDATE parking_slots SET occupied=false;"
docker compose exec -T mqtt-broker sh -c \
 'mosquitto_pub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
  -q 1 -r -n -t barrier/state'
```
