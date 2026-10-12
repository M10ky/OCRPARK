# Fiche de Production — Phase 1 : Arborescence et fondations

- **Nom de la phase** : Phase 1 – Arborescence et fondations
- **Objectif** : Mettre en place l'arborescence complète du projet et les
  fichiers de base (configuration, environnement, orchestration squelette).
- **Date** : 2026-10-12

## Ce qui a été réalisé
- Arborescence complète créée pour les 5 conteneurs + firmware + docs + scripts.
- `.gitignore` couvrant Python, Node/Next.js, Docker, données runtime, modèles
  OCR, IDE, OS, PlatformIO.
- `.env.example` centralisé (PostgreSQL, MQTT, Backend, OCR, Frontend) avec DSN
  et topics MQTT de référence.
- `docker-compose.yml` en **squelette** : projet `smpark`, réseau `smpark-net`,
  volumes nommés, `services: {}` vide + emplacements commentés par phase.
- `README.md` : contexte, architecture cible, schéma de communication,
  prérequis, démarrage rapide, suivi d'avancement.

## Arborescence créée
```
SM-Park/
├── .env.example
├── .gitignore
├── README.md
├── docker-compose.yml
├── backend/app/{api/routes,core,db,models,schemas,services}
├── ocr-service/app/services
├── frontend/
├── mqtt-broker/config
├── database/init
├── firmware/esp32/src
├── docs/fiches-de-production
└── scripts
```

## Fichiers créés / modifiés
| Fichier | État |
|---|---|
| `.gitignore` | créé |
| `.env.example` | créé |
| `README.md` | créé |
| `docker-compose.yml` | créé (squelette) |
| Arborescence (dirs + `.gitkeep`) | créée |

## Checklist de validation
- [x] Arborescence conforme à l'architecture cible
- [x] `docker compose config` parse correctement
- [x] `.env` réel absent du dépôt (seul `.env.example` versionné)
- [x] Aucun secret commité
- [x] Aucun service applicatif encore implémenté (respect du séquencement)

## Tuto de test associé
➡️ [tests/phase-1-tests-fondations.md](../tests/phase-1-tests-fondations.md)

## Prochaine phase
**Phase 2 – Broker MQTT + Base de données**.
