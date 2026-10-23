"""Configuration applicative, chargée depuis l'environnement et le fichier .env."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ParkScan AI"
    app_env: Literal["dev", "prod", "test"] = "dev"
    app_log_level: str = "INFO"
    backend_port: int = 8001

    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "parkscan"
    postgres_user: str = "parkscan"
    postgres_password: str = "change-me"
    db_canary_table: str = "tenants"

    # CSV stocké en chaîne (compatibilité variables d'environnement), exposé en liste.
    cors_origins: str = "http://localhost:5173"

    @property
    def _dsn_tail(self) -> str:
        return (
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url(self) -> str:
        """URL async (asyncpg) pour l'application."""
        return f"postgresql+asyncpg://{self._dsn_tail}"

    @property
    def alembic_database_url(self) -> str:
        """URL sync (psycopg) réservée à Alembic."""
        return f"postgresql+psycopg://{self._dsn_tail}"

    @property
    def sync_dsn(self) -> str:
        """DSN brut pour psycopg (vérifications hors ORM)."""
        return f"postgresql://{self._dsn_tail}"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
