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
- Orchestration (Airflow, profil `mlops`) : http://localhost:8080 (utilisateur et mot de passe `AIRFLOW_ADMIN_*` du `.env`)

Les images de `backend/app/seed/demo_images/` sont des photos libres dont la plaque a été remplacée par une plaque fictive (voir `ATTRIBUTIONS.md` dans ce dossier).

## Parcours de démonstration

1. `make backend-seed` : charge le locataire fictif « Parkings Horizon » (2 sites, 20 résidents, 24 véhicules) et affiche **une seule fois** la clé API de chaque site. Copier celle du premier site dans `.env` (`EDGE_API_KEY=`).
2. Se connecter sur http://localhost:5173 avec `admin@parkings-horizon.example` (mot de passe : `SEED_ADMIN_PASSWORD` du `.env` ; comptes `manager@` et `agent@` sur le même modèle).
3. `make edge-sim` : rejoue les 4 images de démo comme le ferait une caméra. Résultat attendu : un passage autorisé, un refus pour accès désactivé, un passage autorisé avec écart de marque (à valider dans « Écarts de marque »), un refus pour plaque inconnue.
4. Les captures apparaissent en direct dans « Caméras » (image, zones véhicule et plaque détectées, plaque lue avec sa confiance) et dans « Passages » ; la validation d'un écart met à jour la marque déclarée du véhicule et copie l'image vers le jeu d'entraînement.
5. Registre de modèles : `make mlops-up` (MLflow et sa base) puis `make mlops-seed-models` (enregistre les poids de `ml/weights` avec l'alias `production` et recharge le service ML). La page « Modèles » du back-office passe de « Poids locaux » à « Registre MLflow » avec le numéro de version ; sans le profil `mlops`, le service ML se replie sur les poids locaux (ADR-007).
6. Jeu de référence : `make mlops-seed-reference SRC=<dossier avec un sous-dossier par marque>` importe 50 photos par marque (ré-encodées, sans métadonnées) dans le stockage, avec un découpage train/val figé ; chaque entraînement les fusionne aux écarts validés pour que le modèle garde toutes les marques et que la promotion soit jugée sur un jeu de validation qui les couvre toutes (ADR-009). Sans ce jeu, l'entraînement n'utilise que les écarts validés. Source utilisée pour la démo : le sous-ensemble européen de VMMRdb (F. Tafazzoli, H. Frigui, K. Nishiyama, *A Large and Diverse Dataset for Improved Vehicle Make and Model Recognition*, CVPR Workshops 2017 ; usage recherche et enseignement), dont les 22 dossiers correspondent aux marques du classifieur ; les photos ne sont pas versionnées dans ce dépôt.
7. Réentraînement : avec `MIN_DATASET_SIZE=20` dans `.env`, valider une vingtaine d'écarts (rejouer `make edge-sim` autant de fois que nécessaire), puis `make mlops-trigger-training` (ou attendre le dimanche 03:00). Le DAG `brand_training` fige une version du jeu, affine le classifieur dans l'image `trainer` et enregistre un candidat dans MLflow ; le DAG `brand_promotion` le compare à la production sur le même jeu de validation, promeut ou rejette, et recharge le service ML. La page « Modèles » affiche les versions et les décisions (ADR-008, ADR-009).
8. Rétention : `make backend-retention DRY=1` compte les passages au-delà de la durée de conservation (30 jours par défaut, réglable par locataire et par site) ; sans `DRY`, leurs images sont supprimées du stockage et leurs plaques remplacées par un haché. Le backend le fait aussi chaque jour tout seul, et le DAG `retention` le trace dans Airflow (ADR-011, `docs/privacy.md`).

`make help` liste toutes les commandes. Tout passe par `docker compose exec` : rien ne s'exécute hors conteneur.

## Documentation

- [Architecture](docs/architecture.md) : services, flux, données.
- [Runbook](docs/runbook.md) : exploitation au quotidien, incidents, retour arrière d'un modèle.
- [Données personnelles](docs/privacy.md) : inventaire, rétention, anonymisation, droits.
- [Décisions d'architecture](docs/adr/) : ADR-001 à ADR-012.

## Rechargement à chaud sous WSL2

Les bind-mounts depuis `/mnt/c` ne propagent pas les événements de fichiers : `.env.example` active le mode « polling » pour Vite et uvicorn. Sur un système de fichiers Linux natif, ces deux variables peuvent passer à `false`.
