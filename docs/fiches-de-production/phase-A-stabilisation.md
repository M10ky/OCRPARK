# Fiche de Production — Phase A : Stabilisation

- **Nom de la phase** : Phase A – Stabilisation et cohérence API ↔ MQTT ↔ firmware
- **Objectif** : Rendre le système cohérent et stable **avant** d'ajouter des
  fonctionnalités : corriger les bugs bloquants, figer un contrat MQTT unique,
  aligner backend / firmware simulé / `.env` / docs, fournir des smoke tests.
- **Date** : 2026-10-19
- **Périmètre** : corrections de cohérence uniquement (hors frontend métier,
  capteurs/servos réels, modèles `Visit`/`ParkingSlot`, OCR avancé).

## Ce qui a été réalisé

### 1) Bugs bloquants corrigés
| Sujet | Correction |
|---|---|
| `passages.source` trop court | `String(32)` (`models/passage.py`) — `orchestrator:upload` (19 car.) |
| `/register` acceptait `is_admin` | `UserCreate` sans `is_admin` ; route admin protégée `get_current_admin` |
| `/api/passages` filtres non cumulatifs | `.where()` successifs + `date_from` / `date_to` |
| `correlation_id` = plaque (non unique) | UUID du `Passage` + champ `gate` (`orchestrator.py`) |
| OCR exécuté 2× | une seule inférence `read()` puis `pick_best()` (`scan.py`) |
| `frontend/Dockerfile` dépendant de `.next` | build multi-stage autonome + `.dockerignore` |
| `NEXT_PUBLIC_*` au runtime | `build.args` ; webcam déplacée dans `docker-compose.camera.yml` |
| `delay()` bloquant (firmware) | machine à états non bloquante `millis()` + Last Will |
| Typo firmware `MQTT_USEROK` | rétabli `MQTT_USER` (le `-DMQTT_USER` de `secrets.ini` s'applique) |

### 2) Contrat MQTT unique
- `docs/mqtt-contract.md` créé : topics, directions, **QoS 1**, **retain**
  (`parking/state`, `barrier/state`), payloads JSON, règles de nommage,
  mapping API ↔ MQTT ↔ firmware simulé, écarts/limitations.

### 3) Alignement du code sur le contrat
- Backend (`services/mqtt.py`) : souscription/publication **QoS 1**, commande
  `retain=false`, suppression du code mort `publish_json`.
- Firmware (`src/main.cpp`) : écho du `correlation_id` dans le premier
  `barrier/state` (ACK), puis effacé.
- Simulateur (`scripts/barrier_sim.sh`) : écho `correlation_id` + production
  `parking/events` et `parking/state` (`slots`, retain), QoS 1.
- Docs : `docs/tests/phase-2-tests-mqtt-postgresql.md` aligné sur la charge
  `{"slots":[...]}`.
- `.env` local aligné sur `.env.example` (clés réellement lues : `JWT_*`,
  `WS_REQUIRE_AUTH`, `ADMIN_INITIAL_PASSWORD`, `OCR_*`, `NEXT_PUBLIC_BACKEND_URL`).

### 4) Smoke tests
- `scripts/smoke_test.sh` réécrit : health (backend/OCR/DB/MQTT), pub/sub MQTT
  QoS 1, register+login, orchestration upload→décision, ACK barrière simulée.
  Code de sortie non nul au premier échec.

## Fichiers créés / modifiés
| Fichier | État |
|---|---|
| `docs/mqtt-contract.md` | créé (source de vérité MQTT) |
| `scripts/smoke_test.sh` | créé / réécrit |
| `docs/fiches-de-production/phase-A-stabilisation.md` | créé |
| `docs/tests/phase-A-tests-smoke.md` | créé |
| `backend/app/models/passage.py` | modifié (`String(32)`) |
| `backend/app/schemas/auth.py`, `backend/app/api/routes/auth.py` | modifiés (is_admin) |
| `backend/app/api/routes/passages.py` | modifié (filtres + dates) |
| `backend/app/services/orchestrator.py` | modifié (`correlation_id`, `gate`) |
| `backend/app/services/mqtt.py` | modifié (QoS 1, retain, nettoyage) |
| `backend/app/api/routes/ws.py` | modifié (relais MQTT→WS, accept avant 4401) |
| `ocr-service/app/api/routes/scan.py` | modifié (inférence unique) |
| `frontend/Dockerfile`, `frontend/.dockerignore` | modifiés (multi-stage) |
| `docker-compose.yml`, `docker-compose.camera.yml` | modifiés (build args, overlay webcam) |
| `firmware/esp32/src/main.cpp` | modifié (non bloquant, ACK corrélé) |
| `scripts/barrier_sim.sh` | modifié (ACK, events, occupation) |
| `.env.example`, `.env` | alignés (hygiène) |
| `docs/tests/phase-2-tests-mqtt-postgresql.md` | aligné (charge `slots`) |
| `frontend/.env.example` | supprimé (doublon, non versionné) |

## Migration base de données (manuelle, base existante)
`create_all` n'altère pas une colonne existante. Exécuter une fois :
```sql
ALTER TABLE passages ALTER COLUMN source TYPE VARCHAR(32);
```

## Checklist de validation
- [x] Bugs bloquants listés corrigés (vérifiés dans le code réel).
- [x] Aucune fuite de secret : `.env` et `firmware/esp32/secrets.ini` gitignorés,
  absents de l'historique Git.
- [x] Contrat MQTT unique rédigé (`docs/mqtt-contract.md`).
- [x] Backend / firmware / simulateur alignés sur le contrat (topics, QoS, retain,
  `correlation_id`).
- [x] Smoke tests exécutables et verts (health, pub/sub, orchestration, ACK).
- [x] Documentation (fiche + tests) produite.
- [ ] Migration SQL `passages.source` appliquée sur la base en service.

## Limitations assumées
- PubSubClient (ESP32) ne publie qu'en **QoS 0** (retain activé) ; le backend
  tolère cette dégradation (idempotence).
- Le firmware réel ne produit pas encore `parking/state` / `parking/events`
  (capteurs matériels requis) → assuré par le simulateur en Phase A.
- L'orchestrateur n'émet que `action:"open"` (pas de `close` automatique).

## Prochaine phase recommandée
**Phase D — Backend live MQTT / occupation / WebSocket** :
- consommer `parking/state` (occupation) et `parking/events` côté backend ;
- enrichir le WebSocket temps réel (occupation + ACK barrière corrélé au `Passage`) ;
- table(s) d'occupation / `ParkingSlot` et `Visit` (hors scope Phase A).
