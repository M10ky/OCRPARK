# Fiche de Production — Phase 0 : Préparation

- **Nom de la phase** : Phase 0 – Préparation
- **Objectif** : Vérifier l'environnement de développement (WSL2 + Docker +
  chaînes d'outils) et initialiser le dépôt Git du projet SM-Park.
- **Date** : 2026-10-12

## Ce qui a été réalisé
- Audit complet de l'environnement de travail.
- Initialisation du dépôt Git local avec branche par défaut `main`.

## Résultats de vérification de l'environnement

| Composant | Attendu | Détecté | Statut |
|---|---|---|---|
| OS | Windows + WSL2 | WSL2 (kernel `6.6.114.1-microsoft-standard`) | OK |
| Distribution | Linux | Ubuntu-like, GCC 13.2 | OK |
| Git | présent | `2.43.0` | OK |
| Docker Engine | présent | `29.8.2` | OK |
| Docker Compose | v2+ | `v5.5.1` | OK |
| Node.js (frontend) | LTS | `v24.16.0` | OK |
| npm | présent | `11.13.0` | OK |
| Python (services) | 3.10+ | `3.12.3` | OK |
| Espace disque | suffisant | 946 Go libres | OK |
| Config Git | user.name/email | `M10ky` / email défini | OK |

## Fichiers créés / modifiés
| Fichier | État |
|---|---|
| `.git/` | dépôt Git initialisé (`git init -b main`) |

## Checklist de validation
- [x] WSL2 confirmé
- [x] Git, Docker, Compose, Node, npm, Python présents et versionnés
- [x] Dépôt Git créé sur `main`
- [x] Utilisateur ajouté au groupe `docker` (vérifié via `sg docker`)
- [x] `docker run --rm hello-world` fonctionnel

## Points d'attention
- Après `usermod -aG docker $USER`, l'appartenance au groupe n'est active que
  dans une **nouvelle session**. Une session ouverte avant la modification
  nécessite `newgrp docker` ou la commande `sg docker -c "..."`.

## Tuto de test associé
➡️ [tests/phase-0-tests-environnement.md](../tests/phase-0-tests-environnement.md)

## Prochaine phase
**Phase 1 – Arborescence et fondations** : création de l'arborescence complète
et des fichiers de base.
