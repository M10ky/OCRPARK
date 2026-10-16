# Tuto de test — Phase 6 : Frontend Next.js

> Objectif : valider structure, build standalone et intégration Docker du frontend.

## 1. Vérification fichiers
```bash
ls -la /home/miokrako/SM-Park/frontend/package.json /home/miokrako/SM-Park/frontend/next.config.ts /home/miokrako/SM-Park/frontend/Dockerfile /home/miokrako/SM-Park/frontend/.env.example
```

## 2. Build local (optionnel)
```bash
export PATH="/home/miokrako/.nvm/versions/node/v24.16.0/bin:$PATH"
cd /home/miokrako/SM-Park/frontend
npx next build
# Attendu: ✓ Generating static pages, .next/standalone créé
```

## 3. Build Docker
```bash
docker build -t smpark-frontend:test /home/miokrako/SM-Park/frontend
```
Attendu: SUCCESS.

## 4. Test conteneur
```bash
docker run -d --name smpark-frontend-test -p 3000:3000 smpark-frontend:test
sleep 5
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:3000/
docker rm -f smpark-frontend-test
```
Attendu: HTTP 200.

## 5. Via Docker Compose
```bash
docker compose up -d frontend
docker compose ps frontend
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:3000/
docker compose logs --tail 5 frontend
```
