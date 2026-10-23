# ADR-012 : Stack imposée et exceptions signalées

- Statut : accepté
- Date : 23 octobre 2026

## Contexte

ParkScan AI est une refonte complète d'un prototype de certification (monolithe Gradio, SQL brut, MLOps non fonctionnel). Le propriétaire du projet dispose d'une charte de stack fixe, éprouvée en production sur d'autres projets, dont la règle est : régularité avant nouveauté, et tout outil hors socle doit être signalé et justifié.

## Décision

Le socle s'applique tel quel :

- Conteneurisation : Docker Compose multi-services (un service par technologie), réseau `parkscan_net`, Dockerfiles multi-stage `base → dev → prod`, bind-mounts en dev, volumes nommés pour les données, healthchecks, profils `core` (défaut) et `mlops`.
- Backend : Python 3.12, uv (version épinglée identique à celle du poste de développement, 0.11.16, pour garantir la lecture du fichier de verrouillage), `pyproject.toml` (hatchling), FastAPI, Pydantic v2 + pydantic-settings, SQLAlchemy 2.0 async + asyncpg, Alembic + psycopg sync, structlog.
- Frontend : React 18 + Vite 5, TypeScript strict, Tailwind, Zustand, Axios, React Router v6, nginx en prod.
- Base : Postgres 16, exposée sur 5433, JSONB, horodatages avec fuseau.
- Qualité : ruff, pytest + pytest-asyncio + httpx + asgi-lifespan, rollback transactionnel par test.

Exceptions introduites, chacune parce que le socle ne couvre pas le besoin :

| Besoin | Outil | Justification |
|---|---|---|
| Inférence ML | torch CPU, torchvision, ultralytics, fast-plate-ocr[onnx] (OCR `cct-s-v2-global-model`, en RGB, confiance par caractère), opencv-python (entraîné par ultralytics, d'où `libgl1` dans l'image) | Aucun outil d'IA dans le socle ; cœur du produit. Confiné aux images `ml` et `trainer`. Vérifié le 23 octobre 2026 : résolution sur Python 3.12, torch 2.14 CPU, p95 < 350 ms par image sur 4 threads. |
| Authentification SaaS | PyJWT, argon2-cffi | Le socle ne prévoit pas d'auth ; obligatoire en multi-locataires. |
| Stockage d'images | boto3 vers un S3 compatible : **Garage** en dev/démo, S3 managé en production | Les images n'ont pas leur place en base relationnelle. MinIO, prévu initialement, n'est plus distribué (images retirées de Docker Hub et Quay en septembre 2026, projet archivé, dernière image sans correctif de sécurité) : Garage est maintenu, léger, et s'initialise par son API d'administration. |
| Registre de modèles | MLflow (image épinglée, base dédiée, artefacts sur le S3 compatible) | Le réentraînement est une fonctionnalité vendue. |
| Orchestration | Airflow (image légère, sans torch ; entraînement via DockerOperator) | Idem. |
| Agent de bord | OpenCV + httpx | Programme client hors web. |

Écartés : Ray Serve, Gradio, Helm/Kubernetes, Neon, timm (le modèle servi est un EfficientNet torchvision), toute bibliothèque de limitation de débit (implémentée en quelques lignes) et tout générateur de données factices (jeu de démo statique).

## Conséquences

- Un seul fichier Compose, un seul outil par rôle, pas de doublon.
- L'image ML pèse 1,5 à 2 Go (torch CPU) : accepté pour `ml` et `trainer`, interdit ailleurs.
- Toute nouvelle dépendance hors de ce tableau passe par une mise à jour de cet ADR.
