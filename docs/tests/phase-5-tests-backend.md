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
> L'admin initial n'est créé que si `ADMIN_INITIAL_PASSWORD` est défini dans
> `.env` et différent de `admin` (sinon avertissement dans les logs du backend
> et aucun compte admin). Le mot de passe n'est jamais journalisé.

```bash
ADMIN_PWD="$(grep -E '^ADMIN_INITIAL_PASSWORD=' .env | cut -d= -f2-)"
curl -s -X POST http://localhost:8000/api/auth/login \
  -d "username=admin&password=$ADMIN_PWD" \
  -H "Content-Type: application/x-www-form-urlencoded" | python3 -m json.tool
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login -d "username=admin&password=$ADMIN_PWD" -H "Content-Type: application/x-www-form-urlencoded" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/auth/me | python3 -m json.tool
```

### 3bis. Inscription publique ne peut pas s'auto-promouvoir
```bash
# is_admin envoyé mais IGNORE : l'utilisateur est créé non admin
curl -s -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"bob","password":"bobpass123","is_admin":true}' | python3 -m json.tool
TOKEN_BOB=$(curl -s -X POST http://localhost:8000/api/auth/login -d "username=bob&password=bobpass123" -H "Content-Type: application/x-www-form-urlencoded" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s -H "Authorization: Bearer $TOKEN_BOB" http://localhost:8000/api/auth/me | python3 -m json.tool
# Attendu : "is_admin": false
```

### 3ter. Création d'admin (réservée aux admins)
```bash
# Sans token / avec un token non-admin : 401 / 403
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST http://localhost:8000/api/auth/admin/users \
  -H "Content-Type: application/json" -d '{"username":"hacker","password":"x"}'
# Avec le token admin : 201 et is_admin=true
curl -s -X POST http://localhost:8000/api/auth/admin/users \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"username":"admin2","password":"admin2pass"}' | python3 -m json.tool
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
Ouvrir une connexion `ws://localhost:8000/ws/events?token=$TOKEN` (ex. via websocat/wscat).
- Token invalide → fermeture code **4401**.
- Sans token → **accepté** en mode dev (`WS_REQUIRE_AUTH=false`, défaut) ; avec
  `WS_REQUIRE_AUTH=true` (production) → fermeture **4401**.

### 8bis. Relais MQTT → WebSocket
Avec un client WebSocket connecté sur `/ws/events`, publier sur un topic écouté :
```bash
docker compose exec -T mqtt-broker mosquitto_pub -h localhost -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
  -t barrier/state -m '{"state":"open"}'
```
Attendu côté WebSocket : un message JSON
`{"type":"mqtt","topic":"barrier/state","payload":{"state":"open"},"ts":"..."}`.
Le backend logge aussi en `INFO` : « État barrière reçu [barrier/state] : {'state': 'open'} ».

## 9. Sécurité
```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8000/api/plates
```
Attendu 401 (non authentifié).
