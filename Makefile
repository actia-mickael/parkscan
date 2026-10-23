.DEFAULT_GOAL := help
COMPOSE := docker compose
BACKEND := $(COMPOSE) exec backend
FRONTEND := $(COMPOSE) exec frontend

.PHONY: help init up down restart logs ps build clean health \
        backend-shell backend-lint backend-format backend-test backend-migrate backend-revision backend-seed backend-retention \
        frontend-shell frontend-typecheck db-shell \
        ml-shell ml-lint ml-format ml-test ml-logs ml-reload ml-bench ml-fetch-weights edge-sim \
        mlops-up mlops-down mlops-logs mlops-seed-models mlops-trigger-training airflow-logs airflow-shell

# Groupe propriétaire du socket Docker : l'ordonnanceur Airflow en a besoin pour lancer l'image trainer.
export DOCKER_GID ?= $(shell stat -c %g /var/run/docker.sock 2>/dev/null || echo 0)

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

init: ## Prépare .env (si absent) et construit les images
	@test -f .env || (cp .env.example .env && echo ".env créé depuis .env.example : adapte les mots de passe")
	$(COMPOSE) build

up: ## Démarre la stack cœur (db, backend, ml, frontend, garage)
	$(COMPOSE) up -d

down: ## Arrête la stack
	$(COMPOSE) down

restart: ## Redémarre la stack
	$(COMPOSE) restart

logs: ## Suit les journaux de tous les services
	$(COMPOSE) logs -f --tail=100

ps: ## Liste les services et leur état
	$(COMPOSE) ps

build: ## Reconstruit les images
	$(COMPOSE) build

clean: ## Arrête tout et supprime volumes et images locales
	$(COMPOSE) down -v --rmi local --remove-orphans

health: ## Vérifie l'état des services
	@$(COMPOSE) ps --format 'table {{.Service}}\t{{.Status}}'
	@echo "--- backend /health"
	@curl -fsS http://localhost:$${BACKEND_PORT:-8001}/api/v1/health || echo "backend injoignable"
	@echo
	@echo "--- mlflow /health (profil mlops)"
	@curl -fsS http://localhost:$${MLFLOW_PORT:-5000}/health || echo "mlflow arrêté (make mlops-up)"
	@echo
	@echo "--- airflow /api/v2/version (profil mlops)"
	@curl -fsS http://localhost:$${AIRFLOW_PORT:-8080}/api/v2/version || echo "airflow arrêté (make mlops-up)"
	@echo

backend-shell: ## Ouvre un shell dans le backend
	$(BACKEND) bash

backend-lint: ## Lint du backend (ruff)
	$(BACKEND) ruff check .
	$(BACKEND) ruff format --check .

backend-format: ## Formate le backend (ruff)
	$(BACKEND) ruff check --fix .
	$(BACKEND) ruff format .

backend-test: ## Lance les tests backend
	$(BACKEND) pytest -q

backend-migrate: ## Applique les migrations
	$(BACKEND) alembic upgrade head

backend-revision: ## Génère une migration (usage : make backend-revision m="message")
	$(BACKEND) alembic revision --autogenerate -m "$(m)"

backend-seed: ## Charge le jeu de démonstration fictif (idempotent)
	$(BACKEND) python -m app.seed.seed_demo

backend-retention: ## Purge les images et anonymise les plaques au-delà de la rétention (DRY=1 : simulation)
	$(BACKEND) python -m app.jobs.retention $(if $(DRY),--dry-run,)

frontend-shell: ## Ouvre un shell dans le frontend
	$(FRONTEND) sh

frontend-typecheck: ## Vérifie les types TypeScript
	$(FRONTEND) npm run typecheck

db-shell: ## Ouvre psql sur la base
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-parkscan} -d $${POSTGRES_DB:-parkscan}

ML := $(COMPOSE) exec ml
WEIGHTS_BASE_URL ?= https://github.com/actia-mickael/parkscan/releases/download/weights-v1

ml-shell: ## Ouvre un shell dans le service ML
	$(ML) bash

ml-lint: ## Lint du service ML (ruff)
	$(ML) ruff check .
	$(ML) ruff format --check .

ml-format: ## Formate le service ML (ruff)
	$(ML) ruff check --fix .
	$(ML) ruff format .

ml-test: ## Tests du service ML (pipeline simulé ; vrais modèles si poids et images présents)
	$(ML) pytest -q

ml-logs: ## Journaux du service ML
	$(COMPOSE) logs -f --tail=100 ml

ml-reload: ## Recharge les modèles du service ML sans redémarrage
	@curl -fsS -X POST http://localhost:$${ML_PORT:-8002}/models/reload -H "X-Internal-Token: $$(grep '^INTERNAL_TOKEN=' .env | cut -d= -f2)" | head -c 600; echo

ml-bench: ## Banc de latence : 20 appels /infer sur les images de démo, p50 et p95 par étape
	$(ML) python scripts/bench.py --n 20 /opt/demo_images

edge-sim: ## Rejoue les images de démo vers l'API (clé API : KEY=psk_... ou EDGE_API_KEY dans .env)
	EDGE_API_KEY=$(or $(KEY),$(shell grep '^EDGE_API_KEY=' .env | cut -d= -f2)) $(COMPOSE) --profile sim run --rm --build edge-sim $(ARGS)

ml-fetch-weights: ## Télécharge les poids produit (détecteur de plaque, classifieur de marques) dans ml/weights
	@mkdir -p ml/weights
	@for f in plate_detector.pt brand_classifier.pth; do \
	  test -f ml/weights/$$f && echo "ml/weights/$$f présent" || curl -fL -o ml/weights/$$f "$(WEIGHTS_BASE_URL)/$$f"; \
	done

# --- Profil mlops : registre de modèles MLflow --------------------------------------------------

mlops-up: ## Démarre le profil mlops (MLflow, Airflow, image trainer) en plus de la stack cœur
	$(COMPOSE) --profile mlops --profile tools build mlflow airflow-apiserver trainer
	$(COMPOSE) --profile mlops up -d

mlops-down: ## Arrête les services du profil mlops (la stack cœur reste)
	$(COMPOSE) --profile mlops stop airflow-scheduler airflow-dag-processor airflow-apiserver airflow-db mlflow mlflow-db

mlops-logs: ## Journaux de MLflow et des composants Airflow
	$(COMPOSE) --profile mlops logs -f --tail=100 mlflow airflow-scheduler airflow-apiserver airflow-dag-processor

airflow-logs: ## Journaux de l'ordonnanceur Airflow (où s'exécutent les tâches)
	$(COMPOSE) --profile mlops logs -f --tail=200 airflow-scheduler

airflow-shell: ## Ouvre un shell dans l'ordonnanceur Airflow (CLI airflow disponible)
	$(COMPOSE) --profile mlops exec airflow-scheduler bash

mlops-trigger-training: ## Déclenche le DAG d'entraînement (FORCE=true ignore le seuil d'écarts nouveaux)
	@TOKEN=$$(curl -fsS -X POST http://localhost:$${AIRFLOW_PORT:-8080}/auth/token -H 'Content-Type: application/json' \
	  -d "{\"username\":\"$$(grep '^AIRFLOW_ADMIN_USER=' .env | cut -d= -f2)\",\"password\":\"$$(grep '^AIRFLOW_ADMIN_PASSWORD=' .env | cut -d= -f2)\"}" \
	  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])') && \
	curl -fsS -X POST http://localhost:$${AIRFLOW_PORT:-8080}/api/v2/dags/brand_training/dagRuns \
	  -H "Authorization: Bearer $$TOKEN" -H 'Content-Type: application/json' \
	  -d '{"logical_date": null, "conf": {"force": $(or $(FORCE),false)}}' | python3 -c 'import sys,json; d=json.load(sys.stdin); print("run", d["dag_run_id"], d["state"])'

mlops-seed-models: ## Enregistre les poids locaux dans MLflow (alias production) puis recharge le service ML
	$(COMPOSE) exec ml python scripts/seed_mlflow.py
	$(MAKE) ml-reload
