# Tuto de test — Phase 1 : Arborescence et fondations

> Objectif pédagogique : vérifier que la structure du projet est correcte et
> comprendre le rôle de chaque fichier de fondation.

Toutes les commandes se lancent depuis la racine du projet (`SM-Park/`).

---

## 1. Vérifier l'arborescence

```bash
find . -type d -not -path './.git*' | sort
```

- **Attendu** : la présence des dossiers `backend/`, `ocr-service/`,
  `frontend/`, `mqtt-broker/`, `database/`, `firmware/`, `docs/`, `scripts/`.
- **Ce que vous apprenez** : chaque dossier correspond à un futur conteneur
  (séparation des responsabilités). Un service = un dossier = un conteneur.

---

## 2. Vérifier que le dépôt Git est bien initialisé

```bash
git status --short --branch
```

- **Attendu** : `## main` (branche principale) et les fichiers listés en `??`
  (non suivis) tant que rien n'est commité.
- **Ce que vous apprenez** : `??` = fichier non suivi ; `A` = ajouté ;
  `M` = modifié. Rien n'est enregistré dans Git tant que vous ne faites pas
  `git add` + `git commit`.

---

## 3. Comprendre et tester le `.gitignore`

```bash
cat .gitignore
git check-ignore -v .env
```

- **Attendu** : la commande affiche la règle qui ignore `.env` (ex. `.env:1`).
- **Ce que vous apprenez** : `.gitignore` empêche de versionner des fichiers
  sensibles (`.env`) ou volumineux (`node_modules`, modèles OCR). `git
  check-ignore` explique *quelle* règle s'applique — très utile en cas de doute.

Test complémentaire :

```bash
touch .env.local
git status --short | grep .env.local   # ne doit RIEN afficher
rm .env.local
```

---

## 4. Comprendre le fichier `.env.example`

```bash
cat .env.example
```

- **Attendu** : des variables regroupées par service (PostgreSQL, MQTT, Backend,
  OCR, Frontend).
- **Ce que vous apprenez** : `.env.example` est un **modèle** documenté et
  versionné ; le vrai `.env` (avec les secrets) est créé localement et n'est
  jamais poussé sur Git.

---

## 5. Valider le squelette Docker Compose

```bash
docker compose config
```

- **Attendu** : la configuration normalisée (projet `smpark`, réseau
  `smpark-net`, volumes `postgres_data`, `mosquitto_data`, `mosquitto_log`).
- **Ce que vous apprenez** : `docker compose config` valide la syntaxe YAML,
  remplace les variables `${...}` et détecte les erreurs **avant** de démarrer
  quoi que ce soit. Réflexe à adopter après chaque modification du compose.

Si vous obtenez une erreur du type « variable not set », créez d'abord votre
fichier local :

```bash
cp .env.example .env
```

---

## 6. Vérifier qu'aucun secret n'est prêt à être versionné

```bash
git status --porcelain | grep -E '\.env$'   # ne doit rien retourner
```

- **Attendu** : aucune sortie → le `.env` n'apparaîtra pas dans un futur commit.
- **Ce que vous apprenez** : prendre l'habitude de vérifier `git status` avant
  chaque commit évite de fuiter des mots de passe.

---

## Récapitulatif de la checklist Phase 1

| Test | Commande | Résultat attendu |
|---|---|---|
| Arborescence | `find . -type d` | 5 services + support |
| Git | `git status --branch` | sur `main` |
| .gitignore | `git check-ignore -v .env` | règle affichée |
| Compose | `docker compose config` | YAML normalisé, sans erreur |
| Secrets | `git status` | `.env` absent |
