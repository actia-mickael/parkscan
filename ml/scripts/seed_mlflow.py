"""Enregistre les poids locaux (ML_WEIGHTS_DIR) dans le registre MLflow et pose l'alias « production ».

Usage, dans le conteneur ml : python scripts/seed_mlflow.py [--alias production] [--force]

Idempotent : une version portant le même sha256 est réutilisée ; l'alias est (re)posé dessus.
Artefacts d'une version, aux chemins attendus par le service ML (registry.py) :
- brand_classifier : model/checkpoint.pth + model/labels.json
- plate_detector   : model/plate_detector.pt
"""

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import mlflow
import torch
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from mlflow.store.artifact.runs_artifact_repo import RunsArtifactRepository

from parkscan_ml.config import get_settings

EXPERIMENT = "parkscan-models"
ORIGIN = "release:weights-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def brand_labels(path: Path) -> list[str]:
    try:
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    except Exception:
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    return [str(x) for x in checkpoint.get("label_encoder_classes", [])]


def ensure_registered(client: MlflowClient, name: str, description: str) -> None:
    try:
        client.create_registered_model(name, description=description)
        print(f"[seed-mlflow] modèle enregistré créé : {name}")
    except MlflowException as exc:
        if exc.error_code != "RESOURCE_ALREADY_EXISTS":
            raise


def existing_version(client: MlflowClient, name: str, digest: str) -> Any | None:
    for mv in client.search_model_versions(f"name = '{name}'"):
        if mv.tags.get("sha256") == digest:
            return mv
    return None


def register(
    client: MlflowClient,
    *,
    name: str,
    weights: Path,
    artifact_name: str,
    params: dict[str, Any],
    extra_files: dict[str, bytes],
    alias: str,
    force: bool,
) -> Any:
    if not weights.is_file():
        sys.exit(f"[seed-mlflow] poids absents : {weights} (lancer `make ml-fetch-weights`)")
    digest = sha256(weights)
    mv = None if force else existing_version(client, name, digest)
    if mv is None:
        with mlflow.start_run(run_name=f"seed-{name}") as run, tempfile.TemporaryDirectory() as tmp:
            mlflow.log_params({**params, "sha256": digest, "origin": ORIGIN})
            mlflow.set_tags({"seed": "true", "origin": ORIGIN})
            model_dir = Path(tmp) / "model"
            model_dir.mkdir()
            shutil.copyfile(weights, model_dir / artifact_name)
            for filename, data in extra_files.items():
                (model_dir / filename).write_bytes(data)
            mlflow.log_artifacts(str(model_dir), artifact_path="model")
            source = RunsArtifactRepository.get_underlying_uri(f"runs:/{run.info.run_id}/model")
            mv = client.create_model_version(
                name,
                source,
                run.info.run_id,
                tags={"sha256": digest, "origin": ORIGIN, "candidate": "false"},
                description=f"Poids initiaux ({ORIGIN}), sha256 {digest[:12]}",
            )
        print(f"[seed-mlflow] {name} : version {mv.version} créée (run {run.info.run_id[:8]})")
    else:
        print(
            f"[seed-mlflow] {name} : version {mv.version} déjà présente (même sha256), réutilisée"
        )
    client.set_registered_model_alias(name, alias, mv.version)
    print(f"[seed-mlflow] {name}@{alias} -> version {mv.version}")
    return mv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--alias", default=None, help="alias à poser (défaut : ML_MLFLOW_ALIAS)")
    parser.add_argument("--tracking-uri", default=None, help="défaut : ML_MLFLOW_TRACKING_URI")
    parser.add_argument(
        "--force", action="store_true", help="crée une version même si le sha256 existe"
    )
    args = parser.parse_args()

    settings = get_settings()
    uri = args.tracking_uri or settings.mlflow_tracking_uri
    if not uri:
        sys.exit("[seed-mlflow] ML_MLFLOW_TRACKING_URI manquant (ou --tracking-uri)")
    alias = args.alias or settings.mlflow_alias
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    mlflow.set_experiment(EXPERIMENT)
    client = MlflowClient()

    ensure_registered(
        client, settings.mlflow_plate_model, "Détecteur de plaques d'immatriculation (YOLO affiné)"
    )
    ensure_registered(
        client, settings.mlflow_brand_model, "Classifieur de marques (EfficientNet-B0 @224)"
    )

    labels = brand_labels(settings.brand_classifier_path)
    register(
        client,
        name=settings.mlflow_brand_model,
        weights=settings.brand_classifier_path,
        artifact_name="checkpoint.pth",
        params={"arch": "efficientnet_b0", "img_size": 224, "num_classes": len(labels)},
        extra_files={"labels.json": json.dumps(labels, ensure_ascii=False, indent=2).encode()},
        alias=alias,
        force=args.force,
    )
    register(
        client,
        name=settings.mlflow_plate_model,
        weights=settings.plate_detector_path,
        artifact_name="plate_detector.pt",
        params={"arch": "ultralytics-yolo", "task": "detect"},
        extra_files={},
        alias=alias,
        force=args.force,
    )
    print(f"[seed-mlflow] terminé : {uri} (expérience {EXPERIMENT}, alias {alias})")


if __name__ == "__main__":
    main()
