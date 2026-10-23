.DEFAULT_GOAL := help
COMPOSE := docker compose
BACKEND := $(COMPOSE) exec backend
FRONTEND := $(COMPOSE) exec frontend

.PHONY: help init up down restart logs ps build clean health \
        backend-shell backend-lint backend-format backend-test backend-migrate backend-revision backend-seed \
        frontend-shell frontend-typecheck db-shell

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

init: ## Prépare .env (si absent) et construit les images
	@test -f .env || (cp .env.example .env && echo ".env créé depuis .env.example : adapte les mots de passe")
	$(COMPOSE) build

up: ## Démarre la stack cœur (db, backend, frontend, minio)
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

frontend-shell: ## Ouvre un shell dans le frontend
	$(FRONTEND) sh

frontend-typecheck: ## Vérifie les types TypeScript
	$(FRONTEND) npm run typecheck

db-shell: ## Ouvre psql sur la base
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-parkscan} -d $${POSTGRES_DB:-parkscan}
