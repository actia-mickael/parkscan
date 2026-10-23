"""Configuration des DAG, lue dans l'environnement des conteneurs Airflow (voir compose.yaml)."""

import os

BACKEND_URL = os.environ.get("PARKSCAN_BACKEND_URL", "http://backend:8001").rstrip("/")
ML_URL = os.environ.get("PARKSCAN_ML_URL", "http://ml:8002").rstrip("/")
MLFLOW_URL = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000").rstrip("/")
INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN", "")

BRAND_MODEL = os.environ.get("PARKSCAN_BRAND_MODEL", "brand_classifier")
PRODUCTION_ALIAS = os.environ.get("PARKSCAN_PRODUCTION_ALIAS", "production")
PREVIOUS_ALIAS = os.environ.get("PARKSCAN_PREVIOUS_ALIAS", "previous")

TRAINER_IMAGE = os.environ.get("PARKSCAN_TRAINER_IMAGE", "parkscan-trainer:dev")
DOCKER_URL = os.environ.get("PARKSCAN_DOCKER_URL", "unix://var/run/docker.sock")
DOCKER_NETWORK = os.environ.get("PARKSCAN_DOCKER_NETWORK", "parkscan_net")

HTTP_TIMEOUT = float(os.environ.get("PARKSCAN_HTTP_TIMEOUT", "60"))


def trainer_environment() -> dict[str, str]:
    """Variables transmises au conteneur d'entraînement (S3 du jeu de données, MLflow, réglages)."""
    passthrough = (
        "S3_ENDPOINT_URL",
        "S3_ACCESS_KEY",
        "S3_SECRET_KEY",
        "S3_REGION",
        "S3_BUCKET_DATASET",
        "TRAIN_EPOCHS",
        "TRAIN_FREEZE_EPOCHS",
        "TRAIN_BATCH_SIZE",
        "TRAIN_LR",
        "TRAIN_MIN_PER_CLASS",
        "TRAIN_TORCH_THREADS",
    )
    env = {name: os.environ[name] for name in passthrough if name in os.environ}
    env["MLFLOW_TRACKING_URI"] = MLFLOW_URL
    env["ML_MLFLOW_TRACKING_URI"] = MLFLOW_URL
    env["TRAIN_BRAND_MODEL"] = BRAND_MODEL
    env["TRAIN_PRODUCTION_ALIAS"] = PRODUCTION_ALIAS
    return env
