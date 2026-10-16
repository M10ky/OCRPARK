# Tuto de test — Phase 5 : Backend (Logique métier complète)

> Objectif : valider auth JWT, CRUD plaques, orchestration OCR→décision, historique/stats, WebSocket.

## 1. Démarrage
```bash
docker compose up -d --build
docker compose ps
```

## 2. Health
```bash
curl -s http://localhost:8000/api/health/live | python3 -m json.tool
curl -s http://localhost:8000/api/health | python3 -m json.tool
```

## 3. Auth
```bash
curl -s -X POST http://localhost:8000/api/auth/login \
  -d "username=admin&password=admin" \
  -H "Content-Type: application/x-www-form-urlencoded" | python3 -m json.tool
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login -d "username=admin&password=admin" -H "Content-Type: application/x-www-form-urlencoded" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/auth/me | python3 -m json.tool
```

## 4. Plaques autorisées
```bash
curl -s -X POST http://localhost:8000/api/plates -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"plate":"AA123BB","description":"test"}' | python3 -m json.tool
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/plates | python3 -m json.tool
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/plates/AA123BB | python3 -m json.tool
curl -s -X DELETE http://localhost:8000/api/plates/<UUID> -H "Authorization: Bearer $TOKEN" -w "HTTP %{http_code}\n"
```

## 5. Orchestration upload
```bash
python3 -c "
from PIL import Image,ImageDraw
img=Image.new('RGB',(400,120),'white'); d=ImageDraw.Draw(img); d.text((20,40),'AA123BB',fill='black'); img.save('/tmp/aa123bb.png')
print('ok')
"
curl -s -X POST http://localhost:8000/api/orchestrate/upload -H "Authorization: Bearer $TOKEN" -F "file=@/tmp/aa123bb.png" | python3 -m json.tool
```

## 6. Passages & stats
```bash
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/passages?limit=10" | python3 -m json.tool
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/passages/stats | python3 -m json.tool
```

## 7. Orchestration scan (matériel)
```bash
curl -s -X POST http://localhost:8000/api/orchestrate/scan -H "Authorization: Bearer $TOKEN" -w "HTTP %{http_code}\n"
```

## 8. WebSocket
Ouvrir connexion `ws://localhost:8000/ws/events?token=$TOKEN` (ex. via websocat/wscat) — doit accepter. Sans token → fermeture 4401.

## 9. Sécurité
```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8000/api/plates
```
Attendu 401 (non authentifié).
