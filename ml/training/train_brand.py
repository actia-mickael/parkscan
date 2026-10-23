"""Affine le classifieur de marques sur une version du jeu de données et enregistre un candidat MLflow.

Usage : python -m training.train_brand --dataset-version ds-20261023-150000 [--epochs 6]

Étapes : manifeste et crops depuis le S3 → modèle de production (alias MLflow) comme point de
départ → tête étendue aux marques nouvelles (≥ TRAIN_MIN_PER_CLASS images) → affinage (tronc gelé
les premières époques) → évaluation du candidat ET du modèle de production sur le même jeu de
validation (métriques `baseline_*`) → artefacts et version MLflow taguée READY_FOR_PROMOTION.
La dernière ligne de sortie est un résumé JSON lu par le DAG Airflow.
"""

import argparse
import hashlib
import json
import random
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader

from parkscan_ml.brand import ARCH, BRAND_INPUT_SIZE
from training import dataset as ds
from training.evaluate import (
    confusion,
    confusion_png,
    metrics_from_names,
    predict_names,
    write_json,
)
from training.model import (
    extend_head,
    fetch_production_checkpoint,
    load_checkpoint,
    model_from_checkpoint,
    set_backbone_trainable,
    snapshot,
)
from training.settings import TrainerSettings


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def select_labels(
    old_labels: list[str], train_counts: dict[str, int], min_per_class: int
) -> tuple[list[str], dict[str, int]]:
    """Étiquettes du candidat : celles du modèle + marques nouvelles assez représentées."""
    added, dropped = [], {}
    for brand, count in train_counts.items():
        if brand in old_labels:
            continue
        if count >= min_per_class:
            added.append(brand)
        else:
            dropped[brand] = count
    return [*old_labels, *sorted(added)], dropped


def train_one_epoch(
    model: torch.nn.Module, loader: DataLoader, optimizer: torch.optim.Optimizer, device: str
) -> tuple[float, float]:
    model.train()
    criterion = torch.nn.CrossEntropyLoss()
    total_loss, correct, seen = 0.0, 0, 0
    for images, targets in loader:
        images, targets = images.to(device), targets.to(device)
        optimizer.zero_grad()
        logits = model(images)
        loss = criterion(logits, targets)
        loss.backward()
        optimizer.step()
        total_loss += float(loss) * len(targets)
        correct += int((logits.argmax(1) == targets).sum())
        seen += len(targets)
    return (total_loss / seen if seen else 0.0), (correct / seen if seen else 0.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--min-per-class", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args(argv)

    settings = TrainerSettings()
    epochs = args.epochs or settings.epochs
    min_per_class = args.min_per_class or settings.min_per_class
    seed = args.seed if args.seed is not None else settings.seed
    seed_everything(seed)
    if settings.torch_threads:
        torch.set_num_threads(settings.torch_threads)
    device = settings.device
    started = time.perf_counter()

    work = settings.work_dir / args.dataset_version
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    # 1. Jeu de données
    s3 = ds.s3_client(settings)
    samples = ds.fetch_manifest(s3, settings.s3_bucket_dataset, args.dataset_version)
    samples = ds.download(s3, settings.s3_bucket_dataset, samples, work / "data")
    train_samples = [s for s in samples if s.split == "train"]
    val_samples = [s for s in samples if s.split == "val"]
    if not train_samples or not val_samples:
        sys.exit(f"[train] jeu insuffisant : {len(train_samples)} train / {len(val_samples)} val")
    print(
        f"[train] {len(train_samples)} train, {len(val_samples)} val, classes {ds.class_counts(samples)}"
    )

    # 2. Point de départ : production
    base_path, base_info = fetch_production_checkpoint(settings, work)
    if base_path is None:
        sys.exit("[train] aucun modèle de production dans MLflow : lancer `make mlops-seed-models`")
    base_checkpoint = load_checkpoint(base_path)
    baseline_model, old_labels = model_from_checkpoint(base_checkpoint)
    baseline_model.to(device)
    # Seuil compté sur le jeu complet (train + val) : c'est le nombre d'images validées par les opérateurs
    labels, dropped = select_labels(old_labels, ds.class_counts(samples), min_per_class)
    print(
        f"[train] {len(old_labels)} marques connues, {len(labels) - len(old_labels)} ajoutées, écartées {dropped}"
    )

    model, _ = model_from_checkpoint(base_checkpoint)
    model = extend_head(model, old_labels, labels).to(device)

    train_set = ds.CropDataset(train_samples, labels, train=True)
    val_set = ds.CropDataset(val_samples, labels, train=False)
    if len(train_set) == 0 or len(val_set) == 0:
        sys.exit(
            f"[train] aucune image exploitable après sélection des marques "
            f"(train {len(train_set)}, val {len(val_set)}, écartées {dropped}) : "
            f"abaisser TRAIN_MIN_PER_CLASS ou valider davantage d'écarts"
        )
    train_loader = DataLoader(train_set, batch_size=settings.batch_size, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=settings.batch_size)

    # 3. Référence : la production évaluée sur le même jeu de validation (marques inconnues = erreurs)
    truth, top3, _ = predict_names(baseline_model, val_loader, labels, device)
    baseline = metrics_from_names(truth, top3)
    print(f"[train] référence (production v{base_info.get('base_version')}) : {baseline}")

    # 4. Affinage
    import mlflow

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_registry_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.experiment)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=settings.lr, weight_decay=settings.weight_decay
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", factor=0.5, patience=1
    )
    best_state, best_epoch, best_metrics = (
        snapshot(model),
        0,
        metrics_from_names(*predict_names(model, val_loader, labels, device)[:2]),
    )
    summary: dict[str, Any] = {}
    with mlflow.start_run(run_name=f"train-{args.dataset_version}") as run:
        mlflow.log_params(
            {
                "dataset_version": args.dataset_version,
                "epochs": epochs,
                "freeze_epochs": settings.freeze_epochs,
                "batch_size": settings.batch_size,
                "lr": settings.lr,
                "min_per_class": min_per_class,
                "seed": seed,
                "arch": ARCH,
                "img_size": BRAND_INPUT_SIZE,
                "train_samples": len(train_samples),
                "val_samples": len(val_samples),
                "labels_before": len(old_labels),
                "labels_after": len(labels),
                **base_info,
            }
        )
        mlflow.set_tags(
            {
                "candidate": "true",
                "candidate_status": "TRAINING",
                "dataset_version": args.dataset_version,
            }
        )
        for epoch in range(1, epochs + 1):
            set_backbone_trainable(model, epoch > settings.freeze_epochs)
            train_loss, train_acc = train_one_epoch(model, train_loader, optimizer, device)
            truth, top3, val_loss = predict_names(model, val_loader, labels, device)
            val_metrics = metrics_from_names(truth, top3, val_loss)
            scheduler.step(val_metrics["accuracy"])
            mlflow.log_metrics(
                {
                    "train_loss": train_loss,
                    "train_accuracy": train_acc,
                    "val_loss": val_loss,
                    "val_accuracy": val_metrics["accuracy"],
                },
                step=epoch,
            )
            print(
                f"[train] époque {epoch}/{epochs} : train {train_acc:.3f} (perte {train_loss:.3f}) · val {val_metrics}"
            )
            if val_metrics["accuracy"] >= best_metrics.get("accuracy", -1):
                best_state, best_epoch, best_metrics = snapshot(model), epoch, val_metrics

        # 5. Meilleur état : métriques finales, matrice de confusion, checkpoint
        model.load_state_dict(best_state)
        truth, top3, val_loss = predict_names(model, val_loader, labels, device)
        final = metrics_from_names(truth, top3, val_loss)
        pred = [p[0] for p in top3]
        present = sorted(set(truth) | set(pred))
        artifacts = work / "artifacts"
        write_json(
            {"classes": present, "matrix": confusion(truth, pred, present)},
            artifacts / "confusion_matrix.json",
        )
        confusion_png(confusion(truth, pred, present), present, artifacts / "confusion_matrix.png")
        model_dir = artifacts / "model"
        model_dir.mkdir(parents=True, exist_ok=True)
        checkpoint = {
            "model_state_dict": best_state,
            "label_encoder_classes": labels,
            "num_classes": len(labels),
            "epoch": best_epoch,
            "val_acc": round(100 * final["accuracy"], 2),
            "arch": ARCH,
            "img_size": BRAND_INPUT_SIZE,
            "dataset_version": args.dataset_version,
            **base_info,
        }
        torch.save(checkpoint, model_dir / "checkpoint.pth")
        write_json(labels, model_dir / "labels.json")
        digest = sha256(model_dir / "checkpoint.pth")
        metrics = {**final, **{f"baseline_{k}": v for k, v in baseline.items()}}
        mlflow.log_metrics(metrics)
        mlflow.log_artifacts(str(model_dir), artifact_path="model")
        mlflow.log_artifact(str(artifacts / "confusion_matrix.png"))
        mlflow.log_artifact(str(artifacts / "confusion_matrix.json"))
        mlflow.set_tag("candidate_status", "READY_FOR_PROMOTION")

        from mlflow import MlflowClient
        from mlflow.store.artifact.runs_artifact_repo import RunsArtifactRepository

        client = MlflowClient()
        source = RunsArtifactRepository.get_underlying_uri(f"runs:/{run.info.run_id}/model")
        version = client.create_model_version(
            settings.brand_model,
            source,
            run.info.run_id,
            tags={
                "candidate": "true",
                "candidate_status": "READY_FOR_PROMOTION",
                "dataset_version": args.dataset_version,
                "sha256": digest,
                "base_version": base_info.get("base_version", ""),
            },
            description=f"Affinage sur {args.dataset_version} ({len(train_samples)} images, {len(labels)} marques)",
        )
        summary = {
            "name": settings.brand_model,
            "version": int(version.version),
            "run_id": run.info.run_id,
            "source": source,
            "dataset_version": args.dataset_version,
            "metrics": final,
            "baseline_metrics": baseline,
            "labels_count": len(labels),
            "labels_added": [label for label in labels if label not in old_labels],
            "dropped": dropped,
            "best_epoch": best_epoch,
            "seconds": round(time.perf_counter() - started, 1),
        }
    print(f"[train] terminé en {summary['seconds']} s : version {summary['version']} {final}")
    sys.stdout.flush()
    print(json.dumps(summary, ensure_ascii=False))  # dernière ligne : lue par Airflow (XCom)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
