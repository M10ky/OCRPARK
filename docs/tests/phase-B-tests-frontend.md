# Tuto de test — Phase B : Frontend métier

> Objectif : vérifier que l'interface web, la session JWT et le WebSocket
> temps réel fonctionnent, puis vérifier chaque lien réseau du système.
> Contrats de référence : [`docs/websocket-contract.md`](../websocket-contract.md),
> [`docs/mqtt-contract.md`](../mqtt-contract.md).

## 0. Prérequis

```bash
cd /home/miokrako/SM-Park
docker compose up -d --build
```

Le frontend est servi par le conteneur `frontend` (Next.js, port 3000) et
communique **directement** avec le backend (port 8000) : pas de proxy.
`NEXT_PUBLIC_BACKEND_URL` et `NEXT_PUBLIC_WS_URL` sont **figées au build**.

## 1. Lancement automatique (recommandé)

```bash
bash scripts/test_connections.sh   # attendu : 27 OK, 0 FAIL, 0 SKIP
bash scripts/test_ws_events.sh     # attendu : 6 OK, 0 FAIL
bash scripts/smoke_test.sh         # attendu : 13 OK, 0 FAIL, 0 SKIP
```

| Script | Ce qu'il couvre |
|---|---|
| `test_connections.sh` | 10 sections : stack Docker, DNS interne, backend→DB, backend→broker, backend→OCR, frontend→backend, round-trip broker, ports hôte, chemin ESP32 via IP LAN, CORS |
| `test_ws_events.sh` | contrat WS : snapshot `snapshot` / `slots` / `barrier` (exécuté dans le conteneur backend) |
| `smoke_test.sh` | smoke test fonctionnel de bout en bout (phase A, mis à jour pour `/login`) |

## 2. Pages servies

| Page | Commande | Attendu |
|---|---|---|
| Login | `curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/login` | `200` |
| Racine | `curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/` | `307` → `/dashboard` |
| Dashboard | `curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/dashboard` | `200` |

Le HTML de `/login` contient le formulaire (rendu **serveur**, donc visible
sans JavaScript) : « Connexion à la supervision », « Identifiant »,
« Mot de passe », « Se connecter ».

> Le dashboard affiche « Vérification de la session… » dans le HTML serveur :
> c'est attendu, la garde de session s'exécute côté client (DA-2 / DA-5).

```bash
curl -s http://localhost:3000/login | grep -o 'Connexion à la supervision'
```

**Ce que vous apprenez** : une page avec `useSearchParams`/`Suspense` ne peut
plus être pré-rendue statiquement ; lire `window.location` à la soumission
conserve le rendu serveur et le référencement.

## 3. Flux d'authentification

```bash
# 1. Inscription
curl -s -X POST http://localhost:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"ui_$(date +%s)","password":"pass_12345"}'

# 2. Login (FORM-URLCODED, pas JSON)
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -d 'username=ui_1730000000&password=pass_12345' \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

# 3. Session valide
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/auth/me
# attendu : {"username":"...","email":null,"is_active":true,"is_admin":false}

# 4. Session absente
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/auth/me
# attendu : 401
```

| Piège | Symptôme | Traitement (`lib/api.ts`) |
|---|---|---|
| Login JSON | `400`/`422` depuis le formulaire | corps `application/x-www-form-urlencoded` |
| `is_admin` | non renvoyé par le login | ignorer le champ côté frontend |

## 4. Contrat WebSocket (`/ws/events`)

Le test automatisé `scripts/test_ws_events.sh` exécute le scénario complet dans
le conteneur backend (`websockets` + `paho-mqtt` y sont disponibles) :

| Événement | Contenu attendu |
|---|---|
| `snapshot` | état complet à la connexion (`slots`, `visits`, `barrier`) |
| `slots` | `{ id, occupied }` **sans** `label`/`updated_at` |
| `barrier` | `{ state, gate, reason?, correlation_id?, ack_status?, ts }` |

```bash
bash scripts/test_ws_events.sh
```

**Ce que vous apprenez** : le WS exige un token (`?token=`) ; `ack_status`
nul signifie « heartbeat », **pas** « commande acquittée ».

## 5. API dashboard

```bash
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/slots
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/visits/current
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/barrier/state
```

- `/api/slots` → `{ slots: [...], total, occupied, free }` (labels inclus).
- `/api/barrier/state` → état courant + `ack_status` (nul si pas d'ACK).

## 6. Reconstruire après modification du frontend

```bash
npm --prefix frontend run build   # local (node_modules requis)
docker compose up -d --build frontend   # rebuild du conteneur
```

> Les variables `NEXT_PUBLIC_*` sont figées au **build** : un simple
> redémarrage ne les reprend pas, il faut reconstruire l'image.

## 7. Dépannage

| Symptôme | Cause probable |
|---|---|
| Dashboard vide, WS « reconnecting » | backend arrêté, ou `NEXT_PUBLIC_WS_URL` non alignée avec le port 8000 |
| `401` partout après rechargement | JWT purgé (expiration ou backend redémarré sans base persistante) |
| `/login` ne contient plus le formulaire | `useSearchParams`/`Suspense` réintroduit dans la page |
| Pages 404 dans le conteneur | image non reconstruite après ajout de routes |
