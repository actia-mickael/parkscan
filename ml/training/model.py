"""Modèle d'entraînement : checkpoint de production (MLflow), extension de la tête, gel du tronc."""

import copy
import os
from pathlib import Path
from typing import Any

import torch

from parkscan_ml.brand import build_brand_model
from training.settings import TrainerSettings


def load_checkpoint(path: Path) -> dict[str, Any]:
    try:
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    except Exception:
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(checkpoint, dict) or "model_state_dict" not in checkpoint:
        raise ValueError(f"checkpoint {path} : format inattendu (model_state_dict absent)")
    return checkpoint


def checkpoint_labels(checkpoint: dict[str, Any]) -> list[str]:
    labels = [str(x) for x in checkpoint.get("label_encoder_classes", [])]
    if not labels:
        raise ValueError("checkpoint sans étiquettes (label_encoder_classes)")
    return labels


def model_from_checkpoint(checkpoint: dict[str, Any]) -> tuple[torch.nn.Module, list[str]]:
    labels = checkpoint_labels(checkpoint)
    model = build_brand_model(len(labels))
    model.load_state_dict(checkpoint["model_state_dict"])
    model.parkscan_labels = labels  # type: ignore[attr-defined]
    return model, labels


def extend_head(
    model: torch.nn.Module, old_labels: list[str], new_labels: list[str]
) -> torch.nn.Module:
    """Nouvelle couche de sortie pour `new_labels` ; les poids des classes déjà connues sont copiés."""
    old_head: torch.nn.Linear = model.classifier[1]
    new_head = torch.nn.Linear(old_head.in_features, len(new_labels))
    with torch.no_grad():
        for new_index, label in enumerate(new_labels):
            if label in old_labels:
                old_index = old_labels.index(label)
                new_head.weight[new_index] = old_head.weight[old_index]
                new_head.bias[new_index] = old_head.bias[old_index]
    model.classifier[1] = new_head
    model.parkscan_labels = list(new_labels)  # type: ignore[attr-defined]
    return model


def set_backbone_trainable(model: torch.nn.Module, trainable: bool) -> None:
    for parameter in model.features.parameters():
        parameter.requires_grad = trainable


def snapshot(model: torch.nn.Module) -> dict[str, torch.Tensor]:
    """Copie profonde des poids (la copie superficielle du prototype gardait les derniers poids)."""
    return copy.deepcopy(model.state_dict())


def fetch_production_checkpoint(
    settings: TrainerSettings, work_dir: Path
) -> tuple[Path | None, dict[str, str]]:
    """Télécharge le checkpoint pointé par l'alias de production ; (None, {}) s'il n'y en a pas."""
    if not settings.mlflow_tracking_uri:
        return None, {}
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "2")
    import mlflow
    from mlflow import MlflowClient
    from mlflow.exceptions import MlflowException

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_registry_uri(settings.mlflow_tracking_uri)
    client = MlflowClient()
    try:
        version = client.get_model_version_by_alias(settings.brand_model, settings.production_alias)
    except MlflowException as exc:
        if exc.error_code in {"RESOURCE_DOES_NOT_EXIST", "INVALID_PARAMETER_VALUE"}:
            return None, {}
        raise
    target = work_dir / "production" / f"v{version.version}"
    target.mkdir(parents=True, exist_ok=True)
    mlflow.artifacts.download_artifacts(
        artifact_uri=f"models:/{settings.brand_model}/{version.version}", dst_path=str(target)
    )
    found = next((p for p in sorted(target.rglob("checkpoint.pth")) if p.is_file()), None)
    if found is None:
        raise FileNotFoundError(f"checkpoint.pth absent dans la version {version.version}")
    info = {"base_version": str(version.version), "base_run_id": str(version.run_id or "")}
    return found, info
