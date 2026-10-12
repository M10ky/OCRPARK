# SM-Park — Système de Parking Intelligent

Mise à jour complète du projet SM-Park dans une architecture **100 % locale,
conteneurisée et open-source**. L'ESP32 est réduit à un rôle de **nœud IoT**
(capteurs + actionneurs) communiquant via **MQTT** ; toute l'intelligence
(OCR, logique métier, interface) tourne côté serveur.

## Architecture cible

| Conteneur      | Technologie                | Rôle                              |
|----------------|----------------------------|-----------------------------------|
| `frontend`     | Next.js                    | Interface web                     |
| `backend`      | FastAPI                    | API + logique métier + WebSocket  |
| `ocr-service`  | FastAPI + EasyOCR + OpenCV | Capture webcam + OCR              |
| `mqtt-broker`  | Eclipse Mosquitto          | Communication avec l'ESP32        |
| `database`     | PostgreSQL                 | Stockage des données              |

## Schéma de communication

```
ESP32 (capteurs/actionneurs) <--MQTT--> Mosquitto <--MQTT--> Backend (FastAPI)
                                                                 |
                                            WebSocket / REST     |
                                                                 v
                                          Frontend (Next.js)  <-->  OCR (webcam)
                                                                 |
                                                                 v
                                                          PostgreSQL
```

## Prérequis

- Windows 10/11 + WSL2 (Ubuntu) **ou** Linux/macOS
- Docker Engine + Docker Compose v2
- Node.js 20+ et Python 3.10+ (développement local uniquement)
- Utilisateur ajouté au groupe `docker` :
  `sudo usermod -aG docker $USER && newgrp docker`

## Démarrage rapide

```bash
cp .env.example .env      # puis ajuster les secrets
docker compose up -d --build
```

> Les services seront activés progressivement au fil des phases.

## Structure du dépôt

```
SM-Park/
├── backend/          # API FastAPI + logique métier + WebSocket
├── ocr-service/      # Service OCR (webcam + EasyOCR + OpenCV)
├── frontend/         # Interface Next.js
├── mqtt-broker/      # Configuration Eclipse Mosquitto
├── database/         # Scripts d'initialisation PostgreSQL
├── firmware/esp32/   # Firmware ESP32 (MQTT uniquement)
├── docs/             # Documentation + fiches de production
├── scripts/          # Scripts utilitaires
├── docker-compose.yml
└── .env.example
```

## Avancement

- [x] Phase 0 — Préparation
- [x] Phase 1 — Arborescence et fondations
- [x] Phase 2 — Broker MQTT + Base de données
- [x] Phase 3 — Backend FastAPI (structure de base)
- [ ] Phase 4 — Service OCR
- [ ] Phase 5 — Backend : logique métier complète
- [ ] Phase 6 — Frontend Next.js
- [ ] Phase 7 — Firmware ESP32
- [ ] Phase 8 — Intégration et tests complets
- [ ] Phase 9 — Documentation et finalisation

## Licence

Projet de Master — technologies libres / open-source uniquement.
