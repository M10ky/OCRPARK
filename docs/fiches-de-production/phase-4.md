# Fiche de Production — Phase 4 (Revue) : Service OCR

- **Nom de la phase** : Phase 4 (Revue) – Service OCR : finalisation et documentation
- **Objectif** : Revoir l'état actuel du service OCR, clarifier ce qui fonctionne / reste optionnel (webcam), définir les endpoints officiels et leur comportement attendu, rédiger les tests de connexion/fonctionnement et écrire la fiche de production au même format que les phases précédentes.
- **Date** : 2026-10-12

## Contexte
- Phases 0–3 terminées et documentées.
- `smpark-ocr` fonctionnel : container healthy, EasyOCR chargé, `POST /scan/upload` opérationnel.
- `POST /scan` (capture webcam) et `GET /camera/preview` dépendent du périphérique `/dev/video0` (correctement géré en Docker/WSL, instable dans certains contextes sans matériel → comportement normal).
- Architecture cible (rappel) : ocr-service = FastAPI + EasyOCR + OpenCV (capture webcam + OCR).

## Bilan de l'existant OCR
### Fichiers présents
- `ocr-service/app/main.py` : démarrage FastAPI avec `lifespan`, chargement EasyOCR via `asyncio.to_thread(engine.load)`, CORS, enregistrement des routers `health`, `scan`.
- `ocr-service/app/core/config.py` : configuration centralisée (`pydantic-settings`), params caméra (`OCR_CAMERA_INDEX`, `OCR_CAMERA_WIDTH`, `OCR_CAMERA_HEIGHT`), langues, seuil confiance, `allowlist`, CORS.
- `ocr-service/app/services/ocr.py` : `OCREngine` (singleton `engine`) chargé au démarrage, `read(image)` retourne liste détections (texte nettoyé, confiance, box), `read_best(image)` sélectionne meilleur candidat selon seuil+longueur, `ready` flag.
- `ocr-service/app/services/camera.py` : ouverture/fermeture à la demande (robuste WSL), boucles de pré-lecture (5 frames), gestion `CameraError`, `is_available()`.
- `ocr-service/app/api/routes/health.py` : `GET /health/live` (liveness), `GET /health` (état ocr + camera).
- `ocr-service/app/api/routes/scan.py` : `POST /scan` (camera), `POST /scan/upload` (multipart), `GET /camera/preview` (JPEG), validation fichiers/encodage, réponses typées (`ScanResult`, `Detection`).
- `ocr-service/Dockerfile` : `python:3.11-slim`, dépendances système OpenCV, installation PyTorch CPU, installation requirements, pré-téléchargement modèles EasyOCR (en), CMD uvicorn `app.main:app --host 0.0.0.0 --port 8001`.
- `ocr-service/requirements.txt` : fastapi<0.116, uvicorn[standard]<0.35, pydantic-settings<3, python-multipart<0.1, numpy<2, opencv-python-headless<4.11, easyocr<1.8.
- `docker-compose.yml` : service `ocr-service` avec build, ports 8001:8001, `devices: /dev/video0:/dev/video0`, `privileged: true` (WSL), `OCR_CAMERA_INDEX=0`, healthcheck sur `/health/live`.

### État constaté (tests sur l’environnement)
- `GET /health/live` → `{"status":"alive"}` (200).
- `GET /health` → `{"status":"ok","services":{"ocr":"ready","camera":"unavailable"}}` (200). Statut `ok` quand OCR prêt; camera `unavailable` si aucun `/dev/video0` détecté (attendu hors-ligne matériel).
- `POST /scan/upload` : accepte image valide → retourne `ScanResult` (plate/confidence/detections/source), rejette .env → 400 `Image illisible ou format non supporté`. Fonctionnel.
- `POST /scan` : sans caméra → 503 `Impossible d'ouvrir la caméra...`. Comportement attendu.
- `GET /camera/preview` : sans caméra → 503. Comportement attendu.
- Conteneur `smpark-ocr` healthy, EasyOCR chargé au démarrage (lifespan + préchargement Docker).

## Ce qui fonctionne / ce qui reste optionnel
- **Fonctionnel** : chargement EasyOCR, API endpoints, validation upload, encodage JPEG, healthchecks, conteneurisation, configuration via env.
- **Optionnel / dépendant matériel** : capture webcam (`/scan`, `/preview`) — à valider sur station avec `/dev/video0`. Instabilité éventuelle en WSL sans passerelle caméra justifie l’état "instable/non bloquant" remonté.
- **À ne pas reconstruire** : service stable; se concentrer sur consolidation, tests, documentation.

## Endpoints officiels et comportement attendu
| Méthode | Endpoint | Description | Codes | Notes |
|---|---|---|---|---|
| GET | `/health/live` | Liveness probe (Kubernetes/Docker). | 200 → `{"status":"alive"}` | Toujours disponible. |
| GET | `/health` | État global (OCR + caméra). | 200 → `{"status":"ok\|loading","services":{"ocr":"ready\|loading","camera":"available\|unavailable"}}` | `status=ok` si OCR prêt. |
| POST | `/scan/upload` | OCR sur image envoyée (multipart/form-data, champ `file`). | 200 → `ScanResult`; 400 si fichier vide/invalide; 503 si OCR en chargement. | Source `upload:<filename>`. |
| POST | `/scan` | Capture webcam + OCR (capture synchrone). | 200 → `ScanResult`; 503 si OCR en chargement ou caméra indisponible/erreur capture. | Source `camera`. |
| GET | `/camera/preview` | Aperçu JPEG de la webcam (debug/intégration). | 200 image/jpeg; 503 si caméra indisponible; 500 si encodage échoue. | Utilisable pour prévisualisation avant scan. |

Schémas (tels que codés) :
- `Detection` : `{text: str, confidence: float, box: list[list[int]]}`
- `ScanResult` : `{plate: str|null, confidence: float|null, detections: list[Detection], source: str}`

Règles comportementales :
- OCR chargé au démarrage (lifespan) → `engine.ready` true après démarrage réussi.
- `POST /scan/upload` décode via `cv2.imdecode` (OpenCV); rejette si décodage échoue ou contenu vide.
- `CameraService.capture()` ouvre, set largeur/hauteur, lit 5 frames (stabilisation), relâche périphérique systématiquement (`finally`).
- Nettoyage texte : majuscules, espaces normalisés, strip (`_clean_text`).
- Filtrage : ignore détections vides, tri par confiance desc, `read_best` applique `confidence >= threshold` puis maximise `confidence*len(text)`.

## Tests de connexion et de fonctionnement attendus
### A) Vérification conteneurs
```bash
docker compose ps
# attendu: smpark-ocr Up (healthy), smpark-backend Up (healthy), smpark-mqtt Up (healthy), smpark-db Up (healthy)
```

### B) Healthchecks
```bash
curl -s http://localhost:8001/health/live  # {"status":"alive"}
curl -s http://localhost:8001/health      # {"status":"ok","services":{"ocr":"ready","camera":"available|unavailable"}}
```
Critères : 200 OK, `ocr` == `ready`. `camera` peut être `unavailable` sans matériel — acceptable.

### C) Upload OCR (fonctionnel même sans caméra)
Créer une image de test (hors conteneur si cv2/PIL indisponibles, via Python dans env approprié) ou utiliser image existante supportée. Test avec image valide:
```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST "http://localhost:8001/scan/upload" \
  -F "file=@/chemin/vers/image.jpg"
```
Attendu : 200 + `ScanResult` avec `source` commençant par `upload:`, `detections` liste (peut être vide selon image), `plate`/`confidence` null si aucun candidat >= seuil.

Test fichier invalide (.env/text):
```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST "http://localhost:8001/scan/upload" \
  -F "file=@.env"
```
Attendu : 400 `Image illisible ou format non supporté.`

Fichier vide (si simulé) : 400 `Fichier vide.` (logique présente).

### D) Scan depuis caméra (dépend matériel)
```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST "http://localhost:8001/scan"
```
- Si `/dev/video0` présent + accessible → 200 + `ScanResult` source `camera`.
- Sinon → 503 avec message d'erreur caméra (comportement attendu; non bloquant pour cette phase).

### E) Aperçu caméra (dépend matériel)
```bash
curl -I -X GET "http://localhost:8001/camera/preview" 2>&1 | head -5
# ou curl -s -o /tmp/prev.jpg -w "HTTP %{http_code}\n" http://localhost:8001/camera/preview
```
- Si caméra disponible → 200 + `Content-Type: image/jpeg`.
- Sinon → 503.

### F) Documentation OpenAPI
```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8001/docs
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8001/redoc
curl -s http://localhost:8001/openapi.json | jq '.info.title,.info.version' 2>/dev/null | head -2
```
Attendu : 200 pour docs/redoc, titre `SM-Park OCR`, version `0.1.0`.

### G) Logs démarrage
```bash
docker compose logs ocr-service | tail -15
```
Attendu : "Démarrage de SM-Park OCR v0.1.0", "Modèles EasyOCR chargés.", démarrage uvicorn.

## Fichiers créés / modifiés (Phase 4 Revue)
| Fichier | État | Justification |
|---|---|---|
| `docs/fiches-de-production/phase-4.md` | créé (ce document) | Fiche de production Phase 4 au format unifié (bilan, endpoints, tests). |
| `docs/tests/phase-4-tests-ocr.md` | créé | Tuto de tests OCR clair et reproductible (upload, health, preview/scan selon matériel). |

## Checklist de validation
- [x] Bilan de l’existant OCR dressé (fichiers, état runtime).
- [x] Endpoints officiels listés avec codes/comportements attendus.
- [x] Tests de connexion/fonctionnement définis (health, upload, scan, preview, docs).
- [x] Fiche Phase 4 rédigée dans `docs/fiches-de-production/phase-4.md` au même format que phases précédentes.
- [x] Fichier de tests créé `docs/tests/phase-4-tests-ocr.md`.
- [x] Pas de reconstruction globale du service (seulement consolidation/documentation).
- [x] Respect strict des règles : phase par phase, bilan dans docs/, attente validation explicite avant Phase 5.

## Prochaine phase
**Phase 5 – Backend : Logique métier complète** (à ne pas traiter maintenant) :
- Gestion plaques autorisées (CRUD)
- Historique des passages
- Orchestration détection→OCR→décision→commande barrière
- Intégration MQTT (écoute ESP32 + publication commandes)
- WebSocket temps réel
- Authentification JWT
- Routes API complètes
- Tests de connexion/fonctionnement attendus
- Mise à jour `docs/fiches-de-production/phase-5.md`
