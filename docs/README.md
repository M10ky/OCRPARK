# Documentation SM-Park

Ce dossier centralise la documentation technique du projet SM-Park.

## Organisation

```
docs/
├── README.md                       # ce fichier (index)
├── fiches-de-production/           # fiche de production de chaque phase
│   ├── phase-0-preparation.md
│   ├── phase-1-arborescence-fondations.md
│   ├── phase-2-mqtt-postgresql.md
│   └── phase-3-backend-fastapi.md
└── tests/                          # tutos de test par technologie
    ├── phase-0-tests-environnement.md
    ├── phase-1-tests-fondations.md
    ├── phase-2-tests-mqtt-postgresql.md
    └── phase-3-tests-backend.md
```

## Convention

À la fin de **chaque phase** du projet, deux documents sont produits :

1. **Une fiche de production** (`docs/fiches-de-production/`) :
   nom, objectif, réalisations, fichiers créés/modifiés, checklist de validation,
   prochaine phase.
2. **Un tuto de test** (`docs/tests/`) : pour chaque technologie mise en œuvre ou
   modifiée durant la phase, des commandes de vérification accompagnées du
   résultat attendu et de l'explication « ce que vous apprenez ».

## Index des phases

| Phase | Fiche de production | Tuto de test |
|---|---|---|
| 0 – Préparation | [fiche](fiches-de-production/phase-0-preparation.md) | [tests](tests/phase-0-tests-environnement.md) |
| 1 – Arborescence et fondations | [fiche](fiches-de-production/phase-1-arborescence-fondations.md) | [tests](tests/phase-1-tests-fondations.md) |
| 2 – Broker MQTT + Base de données | [fiche](fiches-de-production/phase-2-mqtt-postgresql.md) | [tests](tests/phase-2-tests-mqtt-postgresql.md) |
| 3 – Backend FastAPI (base) | [fiche](fiches-de-production/phase-3-backend-fastapi.md) | [tests](tests/phase-3-tests-backend.md) |

## Technologies utilisées

| Catégorie | Technologie | Rôle |
|---|---|---|
| Conteneurisation | Docker + Docker Compose | Isolation et orchestration des services |
| Broker MQTT | Eclipse Mosquitto | Messagerie ESP32 ↔ backend |
| Base de données | PostgreSQL 16 | Stockage des plaques et de l'historique |
| Backend | FastAPI (Python) | API REST + WebSocket + logique métier |
| OCR | EasyOCR + OpenCV | Reconnaissance de plaques (webcam) |
| Frontend | Next.js (React) | Interface web |
| Firmware | ESP32 (PlatformIO) | Nœud IoT capteurs/actionneurs |
