# Fiche de Production — Phase 3 : Backend FastAPI (structure de base)

- **Nom de la phase** : Phase 3 – Backend FastAPI (structure de base)
- **Objectif** : Mettre en place le service backend : structure applicative,
  connexion à PostgreSQL, connexion au broker MQTT, healthcheck et routes de base,
  puis l'intégrer à Docker Compose.
- **Date** : 2026-10-12

## Ce qui a été réalisé

### Structure applicative
- Architecture en couches : `core/` (config), `db/` (connexion SQLAlchemy),
  `models/` (base déclarative), `schemas/` (Pydantic), `services/` (MQTT),
  `api/routes/` (endpoints).
- **Configuration centralisée** via `pydantic-settings` (`core/config.py`) :
  lecture typée de l'environnement, valeurs par défaut, origines CORS en liste.

### Connexion PostgreSQL
- Moteur **asynchrone** SQLAlchemy 2.0 + `asyncpg` (`db/session.py`), avec
  `pool_pre_ping` et session injectable dans les routes (`get_session`).
- Base déclarative `Base` (`models/base.py`) prête pour les tables de la Phase 5.

### Connexion MQTT
- Client **aiomqtt** en tâche de fond (`services/mqtt.py`) : connexion
  authentifiée, abonnement automatique aux topics (`parking/state`,
  `parking/events`, `barrier/state`), **reconnexion automatique** en cas de coupure.
- Méthode `publish()` exposée pour les futures commandes (barrière).

### API
- `GET /` : informations générales (nom, version, environnement).
- `GET /api/health` : état complet (base + MQTT), renvoie **200** si tout est
  opérationnel, **503** sinon.
- `GET /api/health/live` : *liveness probe* utilisé par le healthcheck Docker.
- Middleware CORS configurable + documentation interactive (`/docs`, `/redoc`).

### Conteneurisation
- `Dockerfile` basé sur `python:3.11-slim`, `requirements.txt` versions bornées,
  `.dockerignore`.
- Service `backend` ajouté au `docker-compose.yml` avec `depends_on`
  (attente des healthchecks `database` et `mqtt-broker`) et son propre healthcheck.

## Fichiers créés / modifiés
| Fichier | État |
|---|---|
| `backend/Dockerfile` | créé |
| `backend/requirements.txt` | créé |
| `backend/.dockerignore` | créé |
| `backend/app/main.py` | créé |
| `backend/app/core/config.py` | créé |
| `backend/app/db/session.py` | créé |
| `backend/app/models/base.py` | créé |
| `backend/app/services/mqtt.py` | créé |
| `backend/app/api/routes/root.py` | créé |
| `backend/app/api/routes/health.py` | créé |
| `backend/app/**/__init__.py` | créés |
| `docker-compose.yml` | modifié (service `backend`) |

## Checklist de validation
- [x] Image `smpark-backend` construite sans erreur
- [x] Conteneur `smpark-backend` **healthy**
- [x] `GET /` renvoie les métadonnées de l'API
- [x] `GET /api/health` → `{"status":"ok","services":{"database":"up","mqtt":"up"}}`
- [x] `GET /api/health/live` → 200
- [x] Documenté OpenAPI disponible sur `/docs`
- [x] Résilience : broker arrêté → health `degraded` (503) puis **reconnexion
  automatique** au redémarrage
- [x] Aucune donnée métier exposée (réservé à la Phase 5)

## Tuto de test associé
➡️ [tests/phase-3-tests-backend.md](../tests/phase-3-tests-backend.md)

## Prochaine phase
**Phase 4 – Service OCR** : structure du microservice OCR, webcam + EasyOCR,
endpoint de scan, intégration Docker.
