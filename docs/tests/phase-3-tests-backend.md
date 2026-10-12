# Tuto de test — Phase 3 : Backend FastAPI

> Objectif pédagogique : comprendre ce qu'est une API FastAPI asynchrone, comment
> elle se connecte à PostgreSQL et MQTT, et savoir la tester de bout en bout.

Toutes les commandes partent de la racine du projet, après :

```bash
docker compose up -d --build
docker compose ps
```

> Si votre terminal n'a pas le groupe `docker` actif, préfixez par `sg docker -c "..."`.

---

## 1. Rappels théoriques

- **FastAPI** est un framework Python qui génère automatiquement une API REST
  (JSON) et sa **documentation OpenAPI**.
- **Uvicorn** est le serveur ASGI qui exécute l'application.
- **SQLAlchemy 2.0 async** + **asyncpg** = accès non bloquant à PostgreSQL.
- **aiomqtt** = client MQTT asynchrone qui tourne en tâche de fond.
- **CORS** : autorise le futur frontend (`http://localhost:3000`) à appeler l'API.

---

## 2. Vérifier que le conteneur tourne

```bash
docker compose ps backend
```

- **Attendu** : `smpark-backend` en **Up (healthy)**.
- **Ce que vous apprenez** : l'état `healthy` provient de l'appel au endpoint
  `/api/health/live` défini dans le `healthcheck` du compose.

---

## 3. Explorer l'API

### Route racine

```bash
curl -s http://localhost:8000/ | python3 -m json.tool
```

- **Attendu** :
  ```json
  { "name": "SM-Park", "version": "0.1.0", "environment": "development",
    "docs": "/docs", "health": "/api/health" }
  ```

### Documentation interactive

Ouvrez dans le navigateur : <http://localhost:8000/docs>

- **Ce que vous apprenez** : FastAPI génère la doc **automatiquement** depuis le
  code (types, résumés). Vous pouvez même tester les endpoints depuis cette page.

### Schéma OpenAPI brut

```bash
curl -s http://localhost:8000/openapi.json | python3 -m json.tool | head -30
```

---

## 4. Tester le healthcheck complet (DB + MQTT)

```bash
curl -s -w "\nHTTP %{http_code}\n" http://localhost:8000/api/health
```

- **Attendu** :
  ```json
  {"status":"ok","services":{"database":"up","mqtt":"up"}}
  HTTP 200
  ```
- **Ce que vous apprenez** : l'endpoint exécute réellement un `SELECT 1` sur
  PostgreSQL et lit l'état de la connexion MQTT. C'est un vrai contrôle de
  santé, pas un simple « ping ».

---

## 5. Vérifier la connexion à PostgreSQL vue par le backend

```bash
docker compose logs backend | grep -i "Démarrage\|MQTT\|startup"
```

- **Attendu** : `Démarrage de SM-Park ...`, `Connecté au broker MQTT ...`,
  `Abonné aux topics : ...`.
- **Ce que vous apprenez** : les logs applicatifs confirment l'ordre de
  démarrage (config → MQTT → serveur prêt).

Test direct de la base avec les identifiants du backend :

```bash
docker compose exec database psql -U smpark -d smpark -c "SELECT current_database(), current_user;"
```

---

## 6. Tester la résilience MQTT (reconnexion automatique)

```bash
# 1) on coupe le broker
docker compose stop mqtt-broker
sleep 10
curl -s -w "\nHTTP %{http_code}\n" http://localhost:8000/api/health
```

- **Attendu** : `"mqtt":"down"` et `HTTP 503` (statut `degraded`).

```bash
# 2) on redémarre le broker
docker compose start mqtt-broker
sleep 10
curl -s -w "\nHTTP %{http_code}\n" http://localhost:8000/api/health
```

- **Attendu** : retour à `"mqtt":"up"` et `HTTP 200`.
- **Ce que vous apprenez** : le backend ne plante pas quand MQTT tombe ; il
  retente la connexion (ici toutes les 5 s) et se rétablit tout seul. C'est
  essentiel en IoT où le réseau est instable.

---

## 7. Inspecter l'image et le conteneur (bonus Docker)

```bash
docker images smpark-backend
docker inspect --format '{{.State.Health.Status}}' smpark-backend
docker compose exec backend python -c "import fastapi, sqlalchemy, aiomqtt; print('deps OK')"
```

- **Attendu** : image listée, `healthy`, et `deps OK`.
- **Ce que vous apprenez** : `docker exec` ouvre un shell/commande **dans** le
  conteneur ; pratique pour vérifier l'environnement d'exécution réel.

---

## Récapitulatif de la checklist Phase 3

| Test | Commande | Résultat attendu |
|---|---|---|
| Conteneur | `docker compose ps backend` | `healthy` |
| Racine | `curl localhost:8000/` | JSON métadonnées |
| Docs | navigateur `/docs` | Swagger généré |
| Health | `curl /api/health` | `ok`, 200 |
| DB/MQTT | health | `database: up`, `mqtt: up` |
| Résilience | stop/start broker | `degraded` puis `ok` |
| Deps | `exec ... import` | `deps OK` |
