# Runbook ParkScan AI

## Démarrage et arrêt

- `make init` (première fois : `.env` + images), `make ml-fetch-weights`, `make up`, `make health`.
- `make backend-seed` : jeu de démonstration (deux locataires, clés API affichées une seule fois).
- Profil MLOps : `make mlops-up` (MLflow, Airflow, image trainer), `make mlops-seed-models`
  (enregistre les poids locaux sous l'alias `production` et recharge le service ML).
- Arrêt : `make down` (la stack) ou `make mlops-down` (seulement MLflow et Airflow).
- Journaux : `make logs`, `make ml-logs`, `make mlops-logs`, `make airflow-logs`.

## Vérifications rapides

- `make health` : état des services, sonde complète du backend (base, stockage, ML), MLflow, Airflow.
- Page « Modèles » du back-office : provenance (`local` ou `mlflow`), versions, décisions.
- `make ml-bench` : latence par étape sur les images de démo (budget p95 : 1 000 ms).

## Incidents courants

| Symptôme | Cause probable | Action |
|---|---|---|
| Passages en « Service ML indisponible » | service ML arrêté ou lent (inférence à froid) | `make ml-logs` ; `ML_TIMEOUT_MS` (1 500 ms par défaut) ; `make ml-reload` |
| Images absentes dans le back-office | Garage arrêté, ou `S3_PUBLIC_ENDPOINT_URL` faux (URLs présignées signées pour le navigateur) | `make health` ; vérifier `.env` |
| Service ML en `local` alors que MLflow tourne | poids non enregistrés, ou MLflow injoignable au démarrage | `make mlops-seed-models` ; `make ml-reload` |
| DAG `brand_training` court-circuité | pas assez d'écarts validés nouveaux (`MIN_DATASET_SIZE`) | valider des écarts, ou `make mlops-trigger-training FORCE=true` |
| Tâche `train` en échec | image `trainer` absente, socket Docker inaccessible (`DOCKER_GID`), jeu vide | `make mlops-up` ; `make airflow-logs` ; le conteneur trainer en échec reste visible (`docker ps -a`) |
| Candidat rejeté | métriques inférieures à la référence sur le jeu de validation | normal : voir la raison dans « Modèles » |
| En dev, une modification de code n'est pas prise en compte (route 404, champ absent) | le rechargement à chaud du backend ou du service ML est mort (sous WSL2 : surveillant de fichiers à court de mémoire, visible dans `make logs`) | `make restart` (ou `docker compose restart backend`) |

## Retour arrière d'un modèle

1. Dans MLflow (http://localhost:5000), modèle `brand_classifier` : poser l'alias `production` sur
   la version voulue (la précédente porte l'alias `previous`).
2. `make ml-reload` : le service ML recharge sans interruption ; vérifier la version dans « Modèles ».
3. Enregistrer la décision si besoin : `POST /api/v1/models/promotions` (jeton interne).

## Données

- Rétention : automatique (backend, chaque `RETENTION_INTERVAL_HOURS`), tracée par le DAG `retention`,
  ou à la main : `make backend-retention DRY=1` puis `make backend-retention`.
- Sauvegardes : volumes `db_data` (métier), `mlflow_db_data`, `airflow_db_data`, `garage_data`
  (images et artefacts). En production : Postgres managé et S3 managé avec leurs sauvegardes.
- Migrations : appliquées au démarrage du backend (`entrypoint.sh`), `make backend-migrate` à la main.

## Secrets

Aucune valeur réelle dans le dépôt. Rotation : `JWT_SECRET` (déconnecte tout le monde),
`INTERNAL_TOKEN` (backend, ML, Airflow à redémarrer ensemble), clés S3 (Garage : `garage/init.py`
les recrée), `ANONYMIZATION_SECRET` (ne pas changer après usage : les hachés existants deviendraient
incomparables).
