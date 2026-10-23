"""Configuration applicative, chargée depuis l'environnement et le fichier .env."""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
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

    # Authentification
    jwt_secret: str = "change-me-jwt-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_minutes: int = 15
    jwt_refresh_days: int = 30
    # Jeton partagé pour les appels internes (Airflow → backend, backend → ML)
    internal_token: str = "change-me-internal-token"

    # Stockage objets compatible S3 (Garage en dev, S3 managé en prod)
    s3_endpoint_url: str = "http://garage:3900"
    s3_public_endpoint_url: str = "http://localhost:3900"  # URLs présignées vues du navigateur
    s3_region: str = "garage"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket_captures: str = "parkscan-captures"
    s3_bucket_dataset: str = "parkscan-dataset"
    # Nombre d'écarts validés (non encore exportés) qui déclenche un réentraînement (défaut global,
    # surchargeable par locataire dans ses réglages ; 20 pour la démo)
    min_dataset_size: int = 500
    presign_expires_seconds: int = 300

    # Service ML
    ml_url: str = "http://ml:8002"
    # Une inférence à froid (service inactif depuis un moment) prend jusqu'à ~750 ms côté ML :
    # 800 ms la faisait échouer en ml_unavailable. Budget p95 produit : 1 000 ms.
    ml_timeout_ms: int = 1500

    # Ingestion
    ingest_rate_per_minute: int = 60
    max_upload_bytes: int = 20 * 1024 * 1024

    # Jeu de démo
    seed_admin_password: str = "admin-change-me"
    seed_manager_password: str = "manager-change-me"
    seed_agent_password: str = "agent-change-me"

    @model_validator(mode="after")
    def _refuse_default_secrets_in_prod(self) -> "Settings":
        if self.app_env != "prod":
            return self
        weak = [
            name
            for name in ("postgres_password", "jwt_secret", "internal_token")
            if getattr(self, name).startswith("change-me")
        ]
        if weak:
            raise ValueError(f"Secrets par défaut interdits en production : {', '.join(weak)}")
        return self

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
