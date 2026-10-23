"""Configuration de l'agent de bord (préfixe EDGE_)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class EdgeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EDGE_", env_file=".env", extra="ignore")

    api_url: str = "http://localhost:8001"
    api_key: str = ""
    timeout_s: float = 1.5
    retries: int = 2
    run_brand: bool = True
