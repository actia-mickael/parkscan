"""Configuration du service ML (préfixe ML_ sur les variables d'environnement)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ML_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: Literal["dev", "prod", "test"] = "dev"
    log_level: str = "INFO"
    internal_token: str = "change-me-internal-token"

    # Poids spécifiques au produit (détecteur de plaque affiné, classifieur de marques)
    weights_dir: Path = Path("/app/weights")
    plate_detector_file: str = "plate_detector.pt"
    brand_classifier_file: str = "brand_classifier.pth"
    # Modèles génériques téléchargés au build de l'image
    generic_models_dir: Path = Path("/opt/models")
    vehicle_detector_name: str = "yolov8s.pt"
    ocr_model_name: str = "cct-s-v2-global-model"

    # Images de démonstration (montées depuis backend/app/seed/demo_images)
    demo_images_dir: Path = Path("/opt/demo_images")

    # Registre de modèles MLflow. auto : MLflow si configuré et joignable, sinon poids locaux ;
    # mlflow : MLflow obligatoire ; local : poids locaux seulement.
    model_source: Literal["auto", "local", "mlflow"] = "auto"
    mlflow_tracking_uri: str = ""
    mlflow_alias: str = "production"
    mlflow_brand_model: str = "brand_classifier"
    mlflow_plate_model: str = "plate_detector"
    mlflow_cache_dir: Path = Path("/app/weights/mlflow")  # artefacts téléchargés, par version
    mlflow_timeout_s: int = 10

    device: str = "cpu"
    torch_threads: int | None = None
    max_concurrency: int = 2
    max_image_bytes: int = 20 * 1024 * 1024

    # Seuils par défaut (le backend peut les surcharger à chaque appel)
    detection_threshold: float = 0.5
    vehicle_threshold: float = 0.25

    @property
    def plate_detector_path(self) -> Path:
        return self.weights_dir / self.plate_detector_file

    @property
    def brand_classifier_path(self) -> Path:
        return self.weights_dir / self.brand_classifier_file

    @property
    def vehicle_detector_path(self) -> Path:
        return self.generic_models_dir / self.vehicle_detector_name


@lru_cache
def get_settings() -> Settings:
    return Settings()
