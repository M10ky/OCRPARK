# Fiche de Production — Phase 5 : Backend (Logique métier complète)

- **Nom de la phase** : Phase 5 – Backend : Logique métier complète
- **Objectif** : Établir la logique métier complète côté backend : modèles (plaques autorisées, passages, utilisateurs), authentification JWT, orchestration détection→OCR→décision→commande barrière, intégration MQTT, WebSocket temps réel, routes API complètes, tests de connexion/fonctionnement attendus.
- **Date** : 2026-10-12

## Ce qui a été réalisé

### 1) Configuration & dépendances
- `backend/app/core/config.py` étendu : `OCR_SERVICE_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `MQTT_TOPIC_BARRIER_COMMAND`.
- `backend/requirements.txt` enrichi : `httpx`, `python-jose[cryptography]`, `passlib[bcrypt]`, `python-multipart`.

### 2) Modèles SQLAlchemy
- `backend/app/models/allowed_plate.py` : `AllowedPlate` (UUID, plate unique/index, description, active, timestamps).
- `backend/app/models/passage.py` : `Passage` (UUID, plate/confidence/recognized/allowed/source/action, barrier_command_sent/barrier_action/mqtt_topic/reason, `ocr_detections` JSON, `raw_image_ref`, `created_at` index).
- `backend/app/models/user.py` : `User` (UUID, username unique/index, email unique/index nullable, `hashed_password`, is_active, is_admin, timestamps).

### 3) Sécurité & dépendances auth
- `backend/app/core/security.py` : hachage bcrypt via `passlib`, création/vérification JWT HS256 (`python-jose`).
- `backend/app/api/deps.py` : `oauth2_scheme`, `get_current_user`, `get_current_admin`.

### 4) Schémas Pydantic
- `backend/app/schemas/auth.py` : `UserCreate`, `UserRead`, `Token`, `TokenData`.
- `backend/app/schemas/plates.py` : `AllowedPlateCreate/Update/Read/Base`.
- `backend/app/schemas/passages.py` : `PassageRead`, `PassageStats`.
- `backend/app/schemas/orchestrate.py` : `OrchestrateResult`.

### 5) Services métier
- `backend/app/services/ws_manager.py` : `ConnectionManager` (connect/disconnect/broadcast) pour WebSocket.
- `backend/app/services/ocr_client.py` : client HTTP vers `ocr-service` (`/scan/upload`, `/scan`), `normalize_plate`.
- `backend/app/services/auth_service.py` : `get_user_by_username`, `authenticate_user`, `create_user`.
- `backend/app/services/orchestrator.py` : `decide_and_act` (OCR→normalisation→lookup whitelist→décision allowed/deny→publication commande barrière si autorisé + MQTT connecté→création Passage→retour résultat unifié).
- `backend/app/db/init_db.py` : création admin dev (`admin`/`ADMIN_INITIAL_PASSWORD`) si absent.

### 6) Routes API
- `backend/app/api/routes/auth.py` : `POST /api/auth/register`, `POST /api/auth/login` (OAuth2 password), `GET /api/auth/me`.
- `backend/app/api/routes/plates.py` : CRUD complet (`GET/POST /api/plates`, `GET/PUT/DELETE /api/plates/{...}`), filtres `active`, normalisation plaques.
- `backend/app/api/routes/passages.py` : `GET /api/passages` (pagination+filtres plate/source/allowed), `GET /api/passages/stats`.
- `backend/app/api/routes/orchestrate.py` : `POST /api/orchestrate/upload` (upload image → OCR → décision → log), `POST /api/orchestrate/scan` (capture ocr-service → décision → log). Protégées par JWT.
- `backend/app/api/routes/ws.py` : `GET /ws/events` (auth optionnelle via `token` query).

### 7) Intégration
- `backend/app/main.py` : enregistrement de tous les routers (auth/plates/passages/orchestrate/ws), démarrage tâche MQTT, CORS.
- `backend/app/services/mqtt.py` : déjà existant (abonnements + publish). Réutilisé pour publication commande barrière.
- `.env.example` : ajout vars JWT/OCR.

## Fichiers créés / modifiés
| Fichier | État |
|---|---|
| `backend/app/core/config.py` | modifié |
| `backend/requirements.txt` | modifié |
| `backend/app/models/allowed_plate.py` | créé |
| `backend/app/models/passage.py` | créé |
| `backend/app/models/user.py` | créé |
| `backend/app/core/security.py` | créé |
| `backend/app/api/deps.py` | créé |
| `backend/app/schemas/auth.py` | créé |
| `backend/app/schemas/plates.py` | créé |
| `backend/app/schemas/passages.py` | créé |
| `backend/app/schemas/orchestrate.py` | créé |
| `backend/app/services/ws_manager.py` | créé |
| `backend/app/services/ocr_client.py` | créé |
| `backend/app/services/auth_service.py` | créé |
| `backend/app/services/orchestrator.py` | créé |
| `backend/app/db/init_db.py` | créé |
| `backend/app/api/routes/auth.py` | créé |
| `backend/app/api/routes/plates.py` | créé |
| `backend/app/api/routes/passages.py` | créé |
| `backend/app/api/routes/orchestrate.py` | créé |
| `backend/app/api/routes/ws.py` | créé |
| `backend/app/main.py` | modifié |
| `.env.example` | modifié |

## Endpoints officiels (résumé)
| Méthode | Route | Auth | Notes |
|---|---|---|---|
| POST | `/api/auth/register` | Public | Création utilisateur (dev). |
| POST | `/api/auth/login` | Public | OAuth2 password → JWT `access_token`. |
| GET | `/api/auth/me` | Bearer | Profil courant. |
| GET/POST | `/api/plates` | Bearer | Lister/créer plaques autorisées. |
| GET/PUT/DELETE | `/api/plates/{id\|plate}` | Bearer | CRUD plaque (UUID ou lookup par plaque). |
| GET | `/api/passages` | Bearer | Historique + filtres/pagination. |
| GET | `/api/passages/stats` | Bearer | Statistiques. |
| POST | `/api/orchestrate/upload` | Bearer | Upload→OCR→décision→log passage. |
| POST | `/api/orchestrate/scan` | Bearer | ocr-service /scan→décision→log passage. |
| WS | `/ws/events` | Optionnel (token query) | Événements temps réel. |

## Orchestration (comportement)
1. Appel OCR-service (upload/scan). 2. Extraction plate+confidence+detections (tolérant formes OCR). 3. Normalisation (uppercase, trim, sans espaces). 4. Lookup `allowed_plates.active==true` (exact). 5. Décision allowed/deny. 6. Si allowed et MQTT connecté → publication `parking/barrier/command` action `open`. 7. Création `Passage` (historisé). 8. Retour `OrchestrateResult`.

## Tests de connexion et de fonctionnement attendus
### A) Démarrage conteneurs
```bash
docker compose up -d --build
docker compose ps
```
Attendu : smpark-backend Up (healthy), smpark-ocr Up (healthy), smpark-mqtt Up (healthy), smpark-db Up (healthy).

### B) Health backend
```bash
curl -s http://localhost:8000/api/health/live  # 200 {"status":"alive"}
curl -s http://localhost:8000/api/health      # 200 {"status":"ok","services":{"database":"up","mqtt":"up"}}
```

### C) Authentification
```bash
# Login admin (mdp depuis ADMIN_INITIAL_PASSWORD, défaut admin)
curl -s -X POST http://localhost:8000/api/auth/login \
  -d "username=admin&password=admin" -H "Content-Type: application/x-www-form-urlencoded"
# Attendu: {"access_token": "...", "token_type": "bearer"}
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login -d "username=admin&password=admin" -H "Content-Type: application/x-www-form-urlencoded" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/auth/me | python3 -m json.tool
```

### D) CRUD plaques autorisées
```bash
curl -s -X POST http://localhost:8000/api/plates -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"plate":"AA123BB","description":"test","active":true}'
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/plates | python3 -m json.tool
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/plates/AA123BB | python3 -m json.tool
```
Attendu : 201 création, liste contient plaque (normalisée sans espaces), GET par plaque OK.

### E) Orchestration upload (OCR→décision)
Avec image test :
```bash
python3 -c "
try:
  from PIL import Image,ImageDraw
  img=Image.new('RGB',(400,120),'white'); d=ImageDraw.Draw(img); d.text((20,40),'AA123BB',fill='black'); img.save('/tmp/test_aa123bb.png')
  print('ok')
except Exception as e: print(e)
"
curl -s -X POST http://localhost:8000/api/orchestrate/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/test_aa123bb.png" | python3 -m json.tool
```
Attendu : `OrchestrateResult` avec `recognized=true`, `allowed=true` (si plaque ajoutée), `action="open"`, `barrier_command_sent` true si MQTT connecté, `detections` présents, `source="orchestrator:upload"`. Un `Passage` créé.

### F) Historique & stats
```bash
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/passages?limit=5" | python3 -m json.tool
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/passages/stats | python3 -m json.tool
```

### G) Orchestration scan (dépend matériel caméra)
```bash
curl -s -X POST http://localhost:8000/api/orchestrate/scan -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```
Même logique que upload mais source `orchestrator:scan`; si caméra indisponible côté ocr-service → retour erreur 503 propagée (attendu).

### H) WebSocket /ws/events (basique)
```bash
python3 -c "
# simple check via httpx/ws? optional; document connexion
pass
"
```
Connexion via `ws://localhost:8000/ws/events?token=$TOKEN` (ou sans token selon besoin). Acceptation OK, broadcast non testé exhaustivement ici.

### I) Sécurité basique
- Sans token sur routes protégées → 401/403 selon OAuth2. Avec token valide → OK.
- Register/login publics OK.

## Fichiers créés / modifiés (Phase 5)
Voir tableau ci-dessus. Tous les ajouts sont non-destructifs vis-à-vis Phase 3.

## Checklist de validation
- [x] Modèles créés (AllowedPlate, Passage, User) et cohérents avec objectifs.
- [x] Auth JWT (register/login/me) fonctionnelle.
- [x] CRUD plaques autorisées complet + normalisation.
- [x] Historique passages + filtres + stats.
- [x] Orchestration upload/scan vers ocr-service.
- [x] Décision + commande barrière MQTT (si autorisé + connecté).
- [x] Journalisation Passage à chaque orchestration.
- [x] WebSocket temps réel configuré.
- [x] Routes protégées par JWT.
- [x] Intégration main + .env.example.
- [x] Respect format phases précédentes, pas de reconstruction globale.

## Prochaine phase
**Phase 6 – Frontend Next.js** (ne pas traiter maintenant) : interface web (auth, tableau de bord, historique, scan/upload, temps réel WS), intégration API backend.
