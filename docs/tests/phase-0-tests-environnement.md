# Tuto de test — Phase 0 : Environnement

> Objectif pédagogique : vérifier que votre poste est prêt à faire tourner tout
> le projet, et comprendre à quoi sert chaque outil.

Toutes les commandes se lancent dans un terminal **WSL (Ubuntu)**.

---

## 1. Vérifier que vous êtes bien dans WSL (et non sous Windows)

```bash
uname -a
grep -i microsoft /proc/version
```

- **Attendu** : le noyau contient `microsoft-standard-WSL2`.
- **Ce que vous apprenez** : WSL2 exécute un vrai noyau Linux virtualisé par
  Windows. Docker et les conteneurs Linux ont besoin de ce noyau.

---

## 2. Vérifier Git

```bash
git --version
git config --global user.name
git config --global user.email
```

- **Attendu** : une version ≥ 2.34, et un nom/email configurés (sinon Git refuse
  de créer des commits).
- **Si vide**, configurez :
  ```bash
  git config --global user.name "Votre Nom"
  git config --global user.email "vous@exemple.com"
  ```
- **Ce que vous apprenez** : l'identité Git est attachée à chaque commit ; elle
  apparaît dans l'historique.

---

## 3. Vérifier Docker et Docker Compose

```bash
docker --version
docker compose version
```

- **Attendu** : `Docker version 2x...` et `Docker Compose version v2+`.
- **Ce que vous apprenez** : *Docker Engine* exécute les conteneurs ;
  *Docker Compose* décrit et orchestre plusieurs conteneurs depuis un seul
  fichier `docker-compose.yml`.

---

## 4. Vérifier l'accès au démon Docker (permissions)

```bash
docker info
```

- **Si vous voyez** `permission denied while trying to connect to the Docker API`,
  votre utilisateur n'est pas dans le groupe `docker` :

  ```bash
  sudo usermod -aG docker $USER
  newgrp docker          # active le groupe dans le terminal courant
  # ou fermez / rouvrez complètement le terminal WSL
  groups                 # doit maintenant afficher "docker"
  ```

- **Astuce dépannage** : dans une session ouverte *avant* la modification, vous
  pouvez préfixer ponctuellement les commandes par `sg docker -c "..."`.
- **Ce que vous apprenez** : l'accès au socket `/var/run/docker.sock` est réservé
  au groupe `docker`. Ajouter l'utilisateur au groupe évite de taper `sudo` à
  chaque commande.

---

## 5. Test de bout en bout de Docker

```bash
docker run --rm hello-world
```

- **Attendu** : le message `Hello from Docker!` suivi d'explications.
- **Ce que vous apprenez** : `docker run` télécharge une image si nécessaire,
  démarre un conteneur, exécute la commande, puis `--rm` supprime le conteneur
  à la fin. C'est la preuve que téléchargement d'images + exécution fonctionnent.

---

## 6. Vérifier les chaînes d'outils applicatives

```bash
node --version     # frontend Next.js
npm --version
python3 --version  # services FastAPI / OCR
df -h .            # espace disque disponible
```

- **Attendu** : Node ≥ 20, npm présent, Python ≥ 3.10, espace disque confortable.
- **Ce que vous apprenez** : Node sert au frontend, Python aux services
  backend/OCR. Dans ce projet, ces outils servent surtout au développement local
  (les conteneurs embarquent leurs propres versions en production).

---

## Récapitulatif de la checklist Phase 0

| Test | Commande | Résultat attendu |
|---|---|---|
| WSL2 | `grep -i microsoft /proc/version` | `microsoft-standard-WSL2` |
| Git | `git --version` | ≥ 2.34 |
| Docker | `docker --version` | ≥ 20 |
| Compose | `docker compose version` | v2+ |
| Permissions | `groups` | contient `docker` |
| Docker E2E | `docker run --rm hello-world` | `Hello from Docker!` |
| Node | `node --version` | ≥ 20 |
| Python | `python3 --version` | ≥ 3.10 |
