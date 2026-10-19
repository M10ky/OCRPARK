# Tuto de test — Phase A : Smoke tests de stabilisation

> Objectif : vérifier en une commande que le système est cohérent
> API ↔ MQTT ↔ firmware simulé, et savoir interpréter chaque résultat.
> Contrat de référence : [`docs/mqtt-contract.md`](../mqtt-contract.md).

## 0. Prérequis
```bash
cd /home/miokrako/SM-Park
docker compose up -d --build
# OCR : le chargement des modèles EasyOCR prend ~40 s après le démarrage.
```
Lancer le smoke test :
```bash
bash scripts/smoke_test.sh
```
Variables surchargeables : `BACKEND_URL`, `OCR_URL`, `FRONTEND_URL`,
`MQTT_HOST`, `MQTT_PORT`, `COMPOSE_FILE`. Les identifiants MQTT sont lus dans `.env`.

## 1. Health (backend / OCR / DB / MQTT)
| Test | Commande | Résultat attendu |
|---|---|---|
| Backend vivant | `curl -s http://localhost:8000/api/health/live` | `{"status":"alive"}` (HTTP 200) |
| Backend complet | `curl -s http://localhost:8000/api/health` | `{"status":"ok","services":{"database":"up","mqtt":"up"}}` (200), sinon 503 |
| OCR vivant | `curl -s http://localhost:8001/health/live` | `{"status":"alive"}` (200) |
| Frontend | `curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/` | `200` |
| DB | via `/api/health` | `"database":"up"` |
| MQTT | via `/api/health` | `"mqtt":"up"` |

> `/health` (OCR) sonde la webcam (lent/bloquant sans caméra) ; le smoke test
> utilise `/health/live` pour la liveness.
> **Ce que vous apprenez** : un healthcheck doit distinguer *liveness* (process
> vivant) de la disponibilité des dépendances (DB, MQTT, caméra).

## 2. Publish / Subscribe MQTT (QoS 1)
```bash
# Aller-retour sur un topic de test (dans le conteneur broker)
docker compose exec -T mqtt-broker mosquitto_sub -h localhost -p 1883 \
  -u smpark -P change_me_mqtt -q 1 -t parking/smoketest -C 1 -W 5 &
docker compose exec -T mqtt-broker mosquitto_pub -h localhost -p 1883 \
  -u smpark -P change_me_mqtt -q 1 -t parking/smoketest -m '{"msg":"smoke"}'
```
- **Attendu** : l'abonné reçoit `{"msg":"smoke"}` (QoS 1).
- **Ce que vous apprenez** : `-C 1` s'arrête après 1 message, `-W` borne l'attente ;
  QoS 1 garantit « au moins une fois ».

## 2bis. Topics du contrat (observation)
```bash
docker compose exec mqtt-broker mosquitto_sub -h localhost -p 1883 \
  -u smpark -P change_me_mqtt -t '#' -v
```
- **Attendu** : `parking/state`, `parking/events`, `barrier/state`,
  `parking/barrier/command` conformes à `docs/mqtt-contract.md`.

## 3. Authentification API
```bash
# Inscription publique (is_admin ignoré)
curl -s -X POST http://localhost:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo","password":"demo_pass_123"}'

# Connexion -> token JWT
curl -s -X POST http://localhost:8000/api/auth/login \
  -d 'username=demo&password=demo_pass_123'
```
- **Attendu** : `register` renvoie `"is_admin":false` ; `login` renvoie
  `{"access_token":"...","token_type":"bearer"}`.
- **Ce que vous apprenez** : le mot de passe du formulaire utilisateur passe par
  un schéma OAuth2 (`form`), pas en JSON.

## 4. Orchestration `upload → décision`
```bash
TOKEN="<access_token de l'étape 3>"
curl -s -X POST "http://localhost:8000/api/orchestrate/upload?gate=entry" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/chemin/vers/image.png;type=image/png"
```
- **Attendu** : HTTP 200, JSON contenant `recognized`, `allowed`, `action`,
  `gate`, `source` (`orchestrator:upload`) et, si autorisée, `correlation_id`.
- **Si plaque refusée** : `action:"deny"` et **aucune** publication MQTT.
- **Ce que vous apprenez** : la décision est persistée (`Passage`) **avant** la
  commande MQTT (jamais de barrière ouverte sans trace).

## 5. Commande barrière simulée → ACK corrélé (le vrai test d'intégration)
Le script `scripts/smoke_test.sh` automatise ce flux :
1. démarre `scripts/barrier_sim.sh` (joue l'ESP32) ;
2. s'abonne à `barrier/state` ;
3. publie une commande avec `correlation_id` ;
4. vérifie que le premier état reçu porte **le même** `correlation_id`.

Manuellement :
```bash
# Terminal 1 : simulateur
docker compose exec -T mqtt-broker sh -s < scripts/barrier_sim.sh

# Terminal 2 : écoute
docker compose exec mqtt-broker mosquitto_sub -h localhost -p 1883 \
  -u smpark -P change_me_mqtt -t barrier/state -v

# Terminal 3 : commande
CID="test-1"
docker compose exec mqtt-broker mosquitto_pub -h localhost -p 1883 \
  -u smpark -P change_me_mqtt -t parking/barrier/command -q 1 \
  -m "{\"action\":\"open\",\"gate\":\"entry\",\"correlation_id\":\"$CID\"}"
```
- **Attendu** :
  - `parking/events` : `{"type":"entry","gate":"entry",...}`
  - `parking/state` : `{"slots":[{"id":1,"occupied":true}]}` (retain)
  - `barrier/state` : `{"state":"opening","correlation_id":"test-1",...}` puis
    `open`, `closing`, `closed` (sans `correlation_id`).
- **Ce que vous apprenez** : corréler une commande à son acquittement via un
  identifiant unique (`correlation_id`) plutôt que la plaque (non unique).

## Résultats de la dernière exécution (environnement de référence)
```
-- Health -- backend/OCR/frontend/database/mqtt        OK
-- MQTT -- publish QoS 1 / subscribe QoS 1             OK
-- API auth -- register / login                        OK
-- Orchestration -- upload / décision                  OK
-- Barrière simulée -- ACK corrélé                     OK
== Bilan : 12 OK, 0 FAIL ==
```
> Si `ocr-service` ou `frontend` échoue en `000` juste après un démarrage :
> attendre la fin du chargement EasyOCR (~40 s) ou `docker compose restart ocr-service`.

## Nettoyage
Le smoke test purge l'état retenu de `barrier/state` avant le test et arrête le
simulateur à la fin. En cas de simulateur résiduel :
```bash
docker compose exec mqtt-broker pkill -f 'mosquitto_sub -h localhost' || true
```
