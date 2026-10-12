1. Écriture du fichier dédié docs/PHASE_04.md
cat > /home/miokrako/SM-Park/docs/PHASE_04.md << 'EOF'
# FICHE DE PRODUCTION - PHASE 4

## 1. Nom de la phase
**PHASE 4 – Scan des plaques (ocr-service)**

## 2. Objectif
Transformer le module de reconnaissance de plaques (Flask + OpenCV + EasyOCR) existant en un microservice **FastAPI** entièrement conteneurisé. L'objectif est de déplacer le traitement de reconnaissance de plaques sur le PC (webcam) dans un conteneur Docker dédié, conformément à l'architecture cible 100 % locale et au rôle réduit de l'ESP32 (nœud IoT uniquement).

## 3. Ce qui a été réalisé

### 3.1 Création du microservice `ocr-service`
- Création complète de l'arborescence `services/ocr-service/`.
- Portage fidèle de la logique Flask + OpenCV + EasyOCR vers FastAPI.
- Conservation stricte de l'algorithme de détection : conversion en niveaux de gris, `bilateralFilter`, `Canny`, détection de contours quadrilatères, extraction de la ROI de la plaque.
- Ajout d'un endpoint de santé pour le monitoring du service.

### 3.2 API FastAPI
- **`GET /healthz`** : Endpoint de healthcheck retournant `{"status":"ok"}`.
- **`GET /scan`** : Endpoint de reconnaissance de plaque via webcam (logique strictement identique à l'ancienne API Flask `/scan`).
- Gestion d'erreurs structurée (retour JSON avec message d'erreur + code HTTP 500 en cas d'échec).
- Logging structuré (INFO/ERROR) pour la traçabilité des tentatives de scan.
- Chargement unique du lecteur EasyOCR au démarrage pour optimiser les performances des scans suivants.

### 3.3 Conteneurisation Docker
- **Dockerfile** optimisé pour OpenCV + EasyOCR (installation des dépendances système nécessaires : `libgl1`, `libglib2.0-0`, `libsm6`, `libxext6`, `libxrender1`, `libgomp1`).
- Image basée sur `python:3.11-slim` pour un bon compromis entre taille et performance.
- Variables d'environnement configurables (`OCR_DEVICE`, `CAM_INDEX`, `LOG_LEVEL`).
- Port exposé `8000`, mappé sur `8002` côté hôte pour éviter les conflits avec les autres services.

### 3.4 Intégration Docker Compose
- Ajout du service `ocr-service` dans `docker-compose.yml`.
- Montage direct du périphérique webcam : `devices: ["/dev/video0:/dev/video0"]` pour autoriser l'accès à la caméra depuis le conteneur.
- Dépendance déclarée vers `mqtt-broker` (préparation à l'intégration future des phases 5/6).
- Connexion au réseau `smpark-net`.
- Redémarrage automatique (`restart: unless-stopped`).
- Variables d'environnement paramétrables.

### 3.5 Documentation du service
- `services/ocr-service/README.md` : Documentation dédiée (tests local/Docker, accès caméra, dépannage, bonnes pratiques de détection).
- `services/ocr-service/.env.example` : Fichier d'exemple des variables d'environnement.

## 4. Fichiers créés / modifiés

### Fichiers créés
- `services/ocr-service/app/__init__.py`
- `services/ocr-service/app/main.py` – API FastAPI (portage Flask → FastAPI + logique OpenCV/EasyOCR)
- `services/ocr-service/requirements.txt` – Dépendances (fastapi, uvicorn[standard], easyocr, opencv-python, numpy, pillow)
- `services/ocr-service/Dockerfile` – Configuration du conteneur avec dépendances système OpenCV
- `services/ocr-service/.env.example` – Variables d'environnement d'exemple
- `services/ocr-service/README.md` – Documentation d'utilisation et de test (local + Docker + webcam)
- `docs/PHASE_04.md` – Fiche de production de la Phase 4

### Fichiers modifiés
- `docker-compose.yml` – Ajout du service `ocr-service` (build, ports `8002:8000`, `devices`, variables d'environnement, `depends_on`, `networks`)

## 5. Checklist de validation

- [x] Arborescence `services/ocr-service/` créée conformément à la structure du projet
- [x] Logique OpenCV/EasyOCR préservée fidèlement par rapport à l'ancien code Flask
- [x] Endpoints `GET /healthz` et `GET /scan` fonctionnels
- [x] Gestion d'erreurs appropriée (messages clairs, codes HTTP cohérents)
- [x] `requirements.txt` minimal, cohérent et fonctionnel
- [x] `Dockerfile` valide (gestion correcte des dépendances système OpenCV)
- [x] `docker-compose.yml` mis à jour sans impacter les services existants
- [x] Accès à la webcam `/dev/video0` correctement configuré pour le conteneur
- [x] Tests locaux validés (`/healthz` et `/scan`)
- [x] Tests Docker validés (`/healthz` et `/scan`)
- [x] Documentation complète et cohérente avec les phases précédentes
- [x] Respect strict des conventions du projet (microservices, nommage, réseau Docker)
- [x] Conformité aux règles de style du projet (pas de commentaires superflus)

## 6. Prochaine phase

**PHASE 5 – Backend FastAPI (API + logique métier + WebSocket)**

- Créer `services/backend/` (FastAPI)
- Développer l'API REST (gestion parkings, places, véhicules, historiques)
- Intégrer WebSocket pour les mises à jour temps réel vers le Frontend
- Connexion à la base de données PostgreSQL
- Intégration avec `ocr-service` (consommation de l'API `/scan` pour automatiser la détection des plaques)
- Connexion MQTT (lecture/écriture des topics ESP32) via `mqtt-broker`
- Endpoints CRUD + logique métier (occupation/désoccupation des places, tarifs, statistiques)
EOF
echo "✓ docs/PHASE_04.md écrit (fichier dédié)"
2. Mise à jour du fichier dédié docs/PHASES.md
python3 << 'PY'
from pathlib import Path

path = Path('/home/miokrako/SM-Park/docs/PHASES.md')
text = path.read_text(encoding='utf-8')

# Bloc Phase 4 à insérer (format identique aux phases précédentes)
block = '''
### PHASE 4 - Scan des plaques (ocr-service) ✅ RÉALISÉE

**Objectif** : Transformer le module OCR (Flask + OpenCV + EasyOCR) en microservice FastAPI conteneurisé avec accès à la webcam.

**Réalisations** :
- Création de `services/ocr-service/` (FastAPI, OpenCV, EasyOCR)
- Endpoints `GET /healthz` et `GET /scan` (logique préservée fidèlement depuis le code original)
- Dockerfile optimisé avec dépendances système OpenCV
- Intégration de `ocr-service` dans `docker-compose.yml` (devices `/dev/video0`, port 8002:8000)
- Documentation complète du service (README + `.env.example`)
- Fiche de production dédiée `docs/PHASE_04.md`

**Fichiers** : 7 créés, 1 modifié (`docker-compose.yml`)
**Statut** : ✅ Validée
'''

# Ajouter à la fin du fichier s'il n'existe pas déjà
if 'PHASE 4 - Scan des plaques' not in text:
    text += block
    path.write_text(text, encoding='utf-8')
    print('✓ docs/PHASES.md mis à jour (ajout section Phase 4)')
else:
    print('✓ docs/PHASES.md déjà à jour')
PY
3. Mise à jour du fichier dédié docs/ROADMAP.md
python3 << 'PY'
from pathlib import Path

path = Path('/home/miokrako/SM-Park/docs/ROADMAP.md')
text = path.read_text(encoding='utf-8')

# Cocher Phase 4 (format cohérent avec les autres)
old = '- [ ] **Phase 4** : Service OCR (EasyOCR + OpenCV)'
new = '- [x] **Phase 4** : Service OCR (EasyOCR + OpenCV)'

if old in text:
    text = text.replace(old, new)
    path.write_text(text, encoding='utf-8')
    print('✓ docs/ROADMAP.md mis à jour ([x] Phase 4)')
else:
    # Tentative alternative si espace différent
    text = text.replace('Phase 4', 'Phase 4').replace('[ ] **Phase 4**', '[x] **Phase 4**')
    path.write_text(text, encoding='utf-8')
    print('✓ docs/ROADMAP.md vérifié/mis à jour')
PY
4. Mise à jour du fichier dédié README.md
python3 << 'PY'
from pathlib import Path

path = Path('/home/miokrako/SM-Park/README.md')
text = path.read_text(encoding='utf-8')

old = '- [ ] **Phase 4** : Service OCR (EasyOCR + OpenCV)'
new = '- [x] **Phase 4** : Service OCR (EasyOCR + OpenCV)'

if old in text:
    text = text.replace(old, new)
    path.write_text(text, encoding='utf-8')
    print('✓ README.md mis à jour ([x] Phase 4)')
else:
    print('⚠ Ligne Phase 4 non trouvée avec le format exact, vérification...')
    # Remplacement plus souple
    text = text.replace('[ ] **Phase 4**', '[x] **Phase 4**')
    path.write_text(text, encoding='utf-8')
    print('✓ README.md mis à jour (remplacement souple)')
PY
5. Vérification des fichiers dédiés
echo "=== Vérification des fichiers dédiés ==="
echo ""
echo "--- docs/PHASE_04.md (en-tête + structure) ---"
head -25 /home/miokrako/SM-Park/docs/PHASE_04.md
echo "..."
echo ""
echo "--- docs/PHASES.md (section Phase 4) ---"
grep -B 1 -A 18 "PHASE 4 - Scan des plaques" /home/miokrako/SM-Park/docs/PHASES.md
echo ""
echo "--- docs/ROADMAP.md (Phase 4) ---"
grep -n "Phase 4" /home/miokrako/SM-Park/docs/ROADMAP.md
echo ""
echo "--- README.md (Phase 4) ---"
grep -n "Phase 4" /home/miokrako/SM-Park/README.md
Récapitulatif
Les écritures ont été faites directement dans les fichiers dédiés :
- ✅ docs/PHASE_04.md – Fichier dédié complet (format strictement identique aux phases précédentes)
- ✅ docs/PHASES.md – Fichier dédié mis à jour avec la section récapitulative Phase 4
- ✅ docs/ROADMAP.md – Fichier dédié mis à jour (Phase 4 cochée)
- ✅ README.md – Fichier dédié mis à jour (état d'avancement Phase 4)