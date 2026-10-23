# ParkScan AI

Plateforme SaaS de contrôle d'accès parking par lecture de plaque, avec vérification de la marque du véhicule et boucle de réentraînement intégrée. Conçue pour un opérateur gérant plusieurs sites.

> Licence : Business Source License 1.1 (voir `LICENSE`). Usage en production commerciale soumis à accord jusqu'à la date de bascule.

## Architecture

- `backend/` : API métier (FastAPI, SQLAlchemy async, Alembic, Postgres 16)
- `frontend/` : back-office opérateur (React 18, Vite, TypeScript, Tailwind, Zustand)
- `ml/` : service d'inférence (YOLO plaque, OCR, YOLO véhicule, classifieur de marques) et code d'entraînement
- `edge/` : agent de bord (caméra IP → API) et simulateur
- `garage/` : stockage objets compatible S3 pour le dev et la démo (S3 managé en production)
- `airflow/`, `mlflow/` : réentraînement et registre de modèles
- `docs/adr/` : décisions d'architecture

## Démarrage

```bash
make init              # crée .env depuis .env.example et construit les images
make ml-fetch-weights  # télécharge les poids des modèles (Release GitHub) dans ml/weights
make up                # démarre db, backend, frontend, ml, garage
make health            # état des services
make backend-seed      # jeu de démonstration fictif
```

Avant le premier `make up`, remplacer dans `.env` les valeurs `change-me` (mots de passe, secrets Garage : les commandes de génération sont en commentaire).

- API : http://localhost:8001/api/docs
- Back-office : http://localhost:5173
- Service ML : http://localhost:8002/docs (`make ml-bench` mesure la latence par étape)
- S3 local (Garage) : http://localhost:3900
- Registre de modèles (MLflow, profil `mlops`) : http://localhost:5000

Les images de `backend/app/seed/demo_images/` sont des photos libres dont la plaque a été remplacée par une plaque fictive (voir `ATTRIBUTIONS.md` dans ce dossier).

## Parcours de démonstration

1. `make backend-seed` : charge le locataire fictif « Parkings Horizon » (2 sites, 20 résidents, 24 véhicules) et affiche **une seule fois** la clé API de chaque site. Copier celle du premier site dans `.env` (`EDGE_API_KEY=`).
2. Se connecter sur http://localhost:5173 avec `admin@parkings-horizon.example` (mot de passe : `SEED_ADMIN_PASSWORD` du `.env` ; comptes `manager@` et `agent@` sur le même modèle).
3. `make edge-sim` : rejoue les 4 images de démo comme le ferait une caméra. Résultat attendu : un passage autorisé, un refus pour accès désactivé, un passage autorisé avec écart de marque (à valider dans « Écarts de marque »), un refus pour plaque inconnue.
4. Les captures apparaissent en direct dans « Caméras » (image, zones véhicule et plaque détectées, plaque lue avec sa confiance) et dans « Passages » ; la validation d'un écart met à jour la marque déclarée du véhicule et copie l'image vers le jeu d'entraînement.
5. Registre de modèles : `make mlops-up` (MLflow et sa base) puis `make mlops-seed-models` (enregistre les poids de `ml/weights` avec l'alias `production` et recharge le service ML). La page « Modèles » du back-office passe de « Poids locaux » à « Registre MLflow » avec le numéro de version ; sans le profil `mlops`, le service ML se replie sur les poids locaux (ADR-007).

`make help` liste toutes les commandes. Tout passe par `docker compose exec` : rien ne s'exécute hors conteneur.

## Rechargement à chaud sous WSL2

Les bind-mounts depuis `/mnt/c` ne propagent pas les événements de fichiers : `.env.example` active le mode « polling » pour Vite et uvicorn. Sur un système de fichiers Linux natif, ces deux variables peuvent passer à `false`.
