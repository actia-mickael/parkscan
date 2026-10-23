#!/usr/bin/env bash
# Applique les migrations, vérifie la table canari (auto-réparation si désynchronisé), puis lance la commande.
set -euo pipefail
cd /app

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

if ! python -m app.db.canary; then
  echo "[entrypoint] table canari absente : réinitialisation de l'historique Alembic puis nouvelle migration"
  alembic stamp base
  alembic upgrade head
  python -m app.db.canary || { echo "[entrypoint] échec : la table canari manque toujours"; exit 1; }
fi

exec "$@"
