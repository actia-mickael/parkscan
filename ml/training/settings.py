"""Réglages de l'entraînement : variables TRAIN_* ; adresses S3 et MLflow partagées (sans préfixe)."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TrainerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRAIN_", extra="ignore")

    epochs: int = 6
    freeze_epochs: int = 2  # époques avec le tronc gelé (seule la tête apprend)
    batch_size: int = 16
    lr: float = 1e-3
    backbone_lr_factor: float = 0.1  # taux du tronc une fois dégelé, relatif à celui de la tête
    weight_decay: float = 1e-4
    min_per_class: int = 20  # images minimum pour qu'une marque inconnue du modèle soit ajoutée
    seed: int = 42
    device: str = "cpu"
    torch_threads: int | None = None
    work_dir: Path = Path("/tmp/parkscan-train")
    brand_model: str = "brand_classifier"
    production_alias: str = "production"
    experiment: str = "parkscan-brand-training"
    # Jeu de référence multi-marques fusionné à chaque entraînement (préfixe S3 ; vide : désactivé)
    reference_prefix: str = "reference"

    mlflow_tracking_uri: str = Field(default="", validation_alias="MLFLOW_TRACKING_URI")
    s3_endpoint_url: str = Field(default="http://garage:3900", validation_alias="S3_ENDPOINT_URL")
    s3_access_key: str = Field(default="", validation_alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(default="", validation_alias="S3_SECRET_KEY")
    s3_region: str = Field(default="garage", validation_alias="S3_REGION")
    s3_bucket_dataset: str = Field(default="parkscan-dataset", validation_alias="S3_BUCKET_DATASET")
