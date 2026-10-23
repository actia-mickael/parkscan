"""Vérifie qu'une table canari existe après migration. Code de sortie 0 si présente, 1 sinon."""

import sys

import psycopg

from app.core.config import get_settings


def main() -> int:
    settings = get_settings()
    with psycopg.connect(settings.sync_dsn) as conn:
        row = conn.execute("SELECT to_regclass(%s)", (settings.db_canary_table,)).fetchone()
    present = row is not None and row[0] is not None
    print(f"[canary] table '{settings.db_canary_table}' : {'présente' if present else 'ABSENTE'}")
    return 0 if present else 1


if __name__ == "__main__":
    sys.exit(main())
