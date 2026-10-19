# Fiche de Production — Phase D : Backend « live »

- **Nom de la phase** : Phase D – Backend live (MQTT consommé, occupation,
  visites, WebSocket, fiabilité barrière).
- **Objectif** : transformer le backend en **cerveau live** du parking.
- **Date** : 2026-10-19.
- **Périmètre** : consommation MQTT réelle, occupation des places, visites
  entrée/sortie, décision enrichie (parking plein), WebSocket temps réel,
  fiabilité commande barrière (ACK + timeout), API dashboard, tests.
- **Hors scope** : frontend métier (Phase B), firmware capteurs/servos réels
  (Phase C), OCR avancé, TLS MQTT, Alembic avancé, multi-parking.
- **Référence** : `docs/mqtt-contract.md` (contrat MQTT),
  `docs/websocket-contract.md` (format WS).

## Étapes réalisées

| Étape | Contenu | Statut |
|---|---|---|
| D.1 | Conception données & flux (modèles, flux MQTT, événements WS, règles) | validée |
| D.2 | Modèles `ParkingSlot` / `Visit` / `BarrierCommand` + seed 3 places | fait |
| D.3 | Consommation MQTT réelle (handlers par topic) | fait |
| D.4 | Orchestration enrichie (capacité, commande, ACK, timeout) | fait |
| D.5 | WebSocket live (+ snapshot à la connexion) | fait |
| D.6 | API dashboard (`slots`, `visits`, `barrier/state`) | fait |
| D.7 | Tests Phase D (9 OK) + non-régression Phase A (12 OK) | fait |
| D.8 | Documentation finale (cette fiche + tests + index) | fait |

## Modèle de données (nouvelles tables — aucune migration)

`create_all` crée les nouvelles tables ; **aucun `ALTER`** sur les tables
existantes.

| Table | Colonnes clés | Rôle |
|---|---|---|
| `parking_slots` | `id` (PK int = id MQTT), `label`, `occupied`, `updated_at` | occupation (reflet capteurs) |
| `visits` | `id` (UUID), `plate`, `entry_gate`, `exit_gate`, `status` (`inside`/`closed`), `entry_at`, `exit_at`, FKs optionnelles `entry_passage_id`/`exit_passage_id` | visites entrée/sortie |
| `barrier_commands` | `correlation_id` (PK = `Passage.id`), `passage_id`, `action`, `gate`, `status` (`pending`/`acknowledged`/`timeout`), `created_at`, `acked_at` | fiabilité commande/ACK |

Seed : `PARKING_SLOT_COUNT` (défaut **3**) places créées au démarrage
(`app/db/init_db.py`, idempotent). Lien `Visit` ↔ `Passage` : rattachement du
dernier passage autorisé du portail (fenêtre 120 s) si la plaque n'est pas fournie.

## Flux MQTT & WebSocket

| Topic (device → backend) | Effet base | Événement WS |
|---|---|---|
| `parking/state` | mise à jour `parking_slots` (idempotent par `id`) | `slots` |
| `parking/events` (`entry`/`exit`) | ouverture/fermeture `Visit` | `visit` |
| `barrier/state` (avec `correlation_id`) | `BarrierCommand` → `acknowledged` | `barrier` |
| `barrier/state` (sans) | mémorise le dernier état | `barrier` |

Sortant : `parking/barrier/command` (`action`, `gate`, `correlation_id` unique).
Décision : non reconnu → deny ; non autorisée → deny ; **parking plein**
(entrée) → deny ; autorisée + place libre → `open`. La sortie n'est jamais
bloquée par la capacité. Format WS : `docs/websocket-contract.md`.

## API dashboard

| Endpoint | Contenu |
|---|---|
| `GET /api/slots` | places + résumé `{slots, total, occupied, free}` |
| `GET /api/visits?status=&plate=&date_from=&date_to=&limit=&offset=` | historique (filtres cumulatifs) |
| `GET /api/visits/current` | visites `inside` |
| `GET /api/barrier/state` | dernier état barrière + dernière `BarrierCommand` |

Toutes protégées par `get_current_user` (Bearer JWT). Réutilise `passages`,
`plates`, `auth`, `ws/events`.

## Fichiers créés / modifiés

| Fichier | État |
|---|---|
| `backend/app/models/parking_slot.py`, `visit.py`, `barrier_command.py` | créés |
| `backend/app/services/mqtt_handlers.py` | créé (handlers par topic + snapshot) |
| `backend/app/services/barrier.py` | créé (timeout ACK) |
| `backend/app/schemas/slots.py`, `visits.py`, `barrier.py` | créés |
| `backend/app/api/routes/slots.py`, `visits.py`, `barrier.py` | créés |
| `docs/websocket-contract.md` | créé (format WS) |
| `docs/tests/phase-D-tests-backend-live.md` | créé |
| `scripts/smoke_test_phase_d.sh` | créé (9 OK) |
| `backend/app/models/__init__.py`, `main.py`, `core/config.py`, `db/init_db.py` | modifiés (modèles, routeurs, settings, seed) |
| `backend/app/services/mqtt.py` | modifié (`_dispatch` par topic) |
| `backend/app/services/orchestrator.py` | modifié (capacité, `BarrierCommand`, timeout) |
| `backend/app/schemas/orchestrate.py` | modifié (`authorized`, `barrier_ack_status`, `total_slots`, `free_slots`) |
| `backend/app/api/routes/ws.py` | modifié (snapshot à la connexion) |
| `docs/mqtt-contract.md` | modifié (champ optionnel `plate` sur `parking/events`) |

## Checklist de validation

- [x] Le backend consomme réellement MQTT (handlers `parking/state`, `parking/events`, `barrier/state`).
- [x] L'occupation des places est en base et exposée (`/api/slots`).
- [x] Les visites entrée/sortie sont tracées (`visits`, `/api/visits`).
- [x] La décision tient compte du parking plein (refus à l'entrée).
- [x] La commande barrière a un `correlation_id` et un ACK (+ timeout).
- [x] Le WebSocket diffuse les événements live (+ snapshot).
- [x] Tests Phase D documentés et reproductibles (`9 OK`).
- [x] Non-régression Phase A (`12 OK`).
- [x] Fiche de production écrite dans `docs/`.
- [x] Aucune migration manuelle requise (nouvelles tables).

## Limitations assumées

- Occupation = reflet des capteurs (`parking/state`) ; sans capteur, `free` n'est
  pas dérivé des visites (fallback non implémenté).
- `BarrierCommand` conserve la **dernière** commande ; l'`/api/barrier/state`
  expose l'état barrière en mémoire (perdu au redémarrage, non persistant).
- L'orchestrateur n'émet que `action:"open"` (pas de `close` automatique).
- Décision « parking plein » basée sur `parking_slots` (pas de réservation de place).
- Le firmware réel ne produit pas encore `parking/state`/`parking/events`
  (assuré par `scripts/barrier_sim.sh`).

## Tests

Voir `docs/tests/phase-D-tests-backend-live.md` :
```bash
bash scripts/smoke_test_phase_d.sh   # 9 OK
bash scripts/smoke_test.sh           # 12 OK (non-régression)
```

## Prochaine phase recommandée

**Phases B (Frontend) et C (Firmware) en parallèle** :

- **Phase B — Frontend Next.js** : dashboard consommant `/api/slots`,
  `/api/visits`, `/api/barrier/state` et le WebSocket `/ws/events`
  (occupation en direct, visites, décisions, état barrière).
- **Phase C — Firmware ESP32** : capteurs d'occupation → `parking/state`,
  détection véhicule → `parking/events`, pilotage servo barrière sur
  `parking/barrier/command` avec ACK `barrier/state` (`correlation_id`),
  en remplacement du simulateur.
