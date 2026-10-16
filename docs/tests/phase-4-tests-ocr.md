# Tuto de test — Phase 4 : Service OCR

> Objectif : valider le fonctionnement du microservice OCR (EasyOCR + OpenCV) de façon reproductible, en distinguant ce qui est indépendant du matériel (upload/health/docs) et ce qui dépend de la webcam (/scan, /camera/preview).

Pré-requis : services démarrés (`docker compose up -d --build`).

## 1. État des conteneurs
```bash
docker compose ps ocr-service
```
Attendu : `smpark-ocr` Up (healthy).

## 2. Healthchecks
```bash
curl -s http://localhost:8001/health/live | python3 -m json.tool
# {"status":"alive"}

curl -s http://localhost:8001/health | python3 -m json.tool
# {"status":"ok","services":{"ocr":"ready","camera":"available|unavailable"}}
```
- `ocr: ready` requis. 
- `camera: unavailable` est normal s'il n'y a pas de `/dev/video0`.

## 3. Documentation OpenAPI
```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8001/docs
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8001/redoc
curl -s http://localhost:8001/openapi.json | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d['info']['title'], d['info']['version'])
"
```
Attendu : 200, `SM-Park OCR 0.1.0`.

## 4. OCR sur image envoyée (indépendant du matériel)
Créer une image de test simple (texte lisible) :
```bash
python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGB',(400,120),'white')
d=ImageDraw.Draw(img); d.text((20,40),'AA123BB',fill='black')
img.save('/tmp/test_plate.png')
print('ok')
"
```
Envoyer l'image :
```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST "http://localhost:8001/scan/upload" \
  -F "file=@/tmp/test_plate.png" | python3 -m json.tool 2>&1 | tail -30
```
Attendu : HTTP 200, structure `ScanResult` avec `source` `upload:test_plate.png`, `detections` non vide (idéalement), `plate`/`confidence` présents si >= seuil.

Cas fichier invalide :
```bash
echo "test" > /tmp/notimg.txt
curl -s -w "\nHTTP %{http_code}\n" -X POST "http://localhost:8001/scan/upload" \
  -F "file=@/tmp/notimg.txt"
```
Attendu : HTTP 400, `{"detail":"Image illisible ou format non supporté."}`

Cas fichier vide (simulation) : HTTP 400 `{"detail":"Fichier vide."}` si contenu vide.

## 5. Capture webcam + OCR (dépend du matériel)
```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST "http://localhost:8001/scan" | python3 -m json.tool 2>&1 | head -20
```
- Avec caméra `/dev/video0` accessible : HTTP 200 + `ScanResult` source `camera`.
- Sans caméra : HTTP 503 + `{"detail":"Impossible d'ouvrir la caméra (index=0). ..."}` (comportement attendu).

## 6. Aperçu webcam (dépend du matériel)
```bash
curl -s -o /tmp/preview.jpg -w "HTTP %{http_code}\n" "http://localhost:8001/camera/preview"
file /tmp/preview.jpg 2>&1 | head -1
```
- Avec caméra : HTTP 200, `JPEG image data`.
- Sans caméra : HTTP 503.

## 7. Logs de démarrage
```bash
docker compose logs --no-log-prefix ocr-service | tail -10
```
Attendus : `Démarrage de SM-Park OCR v0.1.0`, `Modèles EasyOCR chargés.`.

## Notes
- L'état `camera: unavailable` au healthcheck n'est pas un échec fonctionnel (OCR reste opérationnel via `/scan/upload`).
- Comportement caméra instable en WSL2 sans matériel est connu et documenté ici (non bloquant).
