# Fiche de Production — Phase 2 : Broker MQTT + Base de données

- **Nom de la phase** : Phase 2 – Broker MQTT + Base de données
- **Objectif** : Fournir les deux briques d'infrastructure (messagerie MQTT
  authentifiée et stockage PostgreSQL initialisé) et les intégrer à
  l'orchestration Docker.
- **Date** : 2026-10-12

## Ce qui a été réalisé
- **Mosquitto** configuré : persistance, logs (stdout + fichier),
  **authentification obligatoire** (`allow_anonymous false`), listener MQTT
  `1883` et listener WebSockets `9001`.
- **Entrypoint d'authentification** : génération automatique du fichier
  `passwd` au démarrage à partir de `MQTT_USERNAME`/`MQTT_PASSWORD` (aucun mot
  de passe en clair versionné).
- **PostgreSQL 16** : script d'init créant les extensions `uuid-ossp` +
  `pgcrypto` et fixant la timezone `Indian/Antananarivo` sur la base et
  `template1`. Le schéma métier reste géré par les modèles SQLAlchemy (Phase 5).
- **docker-compose.yml** : ajout des services `mqtt-broker` et `database` avec
  `restart`, réseaux, volumes nommés et **healthchecks**.

## Fichiers créés / modifiés
| Fichier | État |
|---|---|
| `mqtt-broker/config/mosquitto.conf` | créé |
| `mqtt-broker/entrypoint.sh` | créé |
| `database/init/00_init.sql` | créé |
| `docker-compose.yml` | modifié (services `mqtt-broker` + `database`) |
| `.env` | créé localement (**gitignoré, non versionné**) |

## Checklist de validation
- [x] `docker compose config` valide
- [x] Conteneur `smpark-mqtt` **healthy** (`0.0.0.0:1883`, `9001`)
- [x] Conteneur `smpark-db` **healthy** (`0.0.0.0:5432`)
- [x] Publication authentifiée MQTT : OK (`hello`)
- [x] Souscription authentifiée MQTT : OK
- [x] Accès anonyme **refusé** (`Connection Refused: not authorised`)
- [x] PostgreSQL 16.15 opérationnel, extensions `uuid-ossp` + `pgcrypto` présentes
- [x] Timezone `Indian/Antananarivo` appliquée
- [x] Aucun secret commité (fichier `passwd` généré dans le volume `mosquitto_data`)

## Tuto de test associé
➡️ [tests/phase-2-tests-mqtt-postgresql.md](../tests/phase-2-tests-mqtt-postgresql.md)

## Prochaine phase
**Phase 3 – Backend FastAPI (structure de base)** : connexion PostgreSQL, connexion
MQTT, healthcheck et routes de base.
