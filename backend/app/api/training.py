"""Réentraînement (appels internes d'Airflow) : préparation, échantillons, version du jeu de données.

Le jeu est cumulatif : chaque version reprend tous les écarts validés (nouveaux et déjà exportés).
« Prêt » signifie qu'assez d'écarts nouveaux se sont accumulés depuis la dernière version.
"""

import json
import random
from datetime import UTC, datetime

from fastapi import APIRouter, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from app.api.deps import InternalDep, SessionDep, get_storage
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.mismatch_review import MismatchReview, ReviewStatus
from app.schemas.training import (
    DatasetBuildRequest,
    DatasetBuildResult,
    TrainingReadiness,
    TrainingSample,
)

router = APIRouter(prefix="/training", tags=["training"])
log = get_logger(__name__)

LABELED = (ReviewStatus.validated, ReviewStatus.exported)


def _labeled_query():
    return (
        select(MismatchReview)
        .where(
            MismatchReview.status.in_(LABELED),
            MismatchReview.dataset_key.is_not(None),
            MismatchReview.final_brand.is_not(None),
        )
        .order_by(MismatchReview.reviewed_at, MismatchReview.id)
    )


@router.get("/readiness", response_model=TrainingReadiness)
async def readiness(_: InternalDep, session: SessionDep) -> TrainingReadiness:
    reviews = list(await session.scalars(_labeled_query()))
    by_brand: dict[str, int] = {}
    for r in reviews:
        by_brand[r.final_brand or "?"] = by_brand.get(r.final_brand or "?", 0) + 1
    new = sum(1 for r in reviews if r.status == ReviewStatus.validated)
    threshold = get_settings().min_dataset_size
    return TrainingReadiness(
        new_validated=new,
        total_labeled=len(reviews),
        min_dataset_size=threshold,
        ready=new >= threshold,
        by_brand=dict(sorted(by_brand.items())),
    )


@router.get("/samples", response_model=list[TrainingSample])
async def samples(_: InternalDep, session: SessionDep) -> list[TrainingSample]:
    reviews = await session.scalars(_labeled_query())
    return [
        TrainingSample(
            id=r.id,
            tenant_id=r.tenant_id,
            brand=r.final_brand or "?",
            key=r.dataset_key or "",
            exported=r.status == ReviewStatus.exported,
            dataset_version=r.dataset_version,
        )
        for r in reviews
    ]


@router.post("/datasets", response_model=DatasetBuildResult, status_code=status.HTTP_201_CREATED)
async def build_dataset(
    request: Request, payload: DatasetBuildRequest, _: InternalDep, session: SessionDep
) -> DatasetBuildResult:
    """Fige une version du jeu : manifeste (train/val stratifié, graine fixe) + résumé sur le S3,
    et marque « exporté » les écarts qui y entrent pour la première fois."""
    settings = get_settings()
    reviews = list(await session.scalars(_labeled_query()))
    by_brand: dict[str, list[MismatchReview]] = {}
    for r in reviews:
        by_brand.setdefault(r.final_brand or "?", []).append(r)

    version = datetime.now(UTC).strftime("ds-%Y%m%d-%H%M%S")
    rng = random.Random(payload.seed)
    lines: list[dict[str, str]] = []
    classes: dict[str, int] = {}
    dropped: dict[str, int] = {}
    train = val = 0
    for brand in sorted(by_brand):
        items = sorted(by_brand[brand], key=lambda r: str(r.id))
        if len(items) < payload.min_per_class:
            dropped[brand] = len(items)
            continue
        rng.shuffle(items)
        n_val = max(1, round(len(items) * payload.val_ratio)) if len(items) >= 2 else 0
        for index, r in enumerate(items):
            split = "val" if index < n_val else "train"
            lines.append(
                {"key": r.dataset_key or "", "brand": brand, "split": split, "review_id": str(r.id)}
            )
            if split == "val":
                val += 1
            else:
                train += 1
        classes[brand] = len(items)

    manifest_key = f"versions/{version}/manifest.jsonl"
    summary_key = f"versions/{version}/summary.json"
    summary = {
        "dataset_version": version,
        "created_at": datetime.now(UTC).isoformat(),
        "seed": payload.seed,
        "val_ratio": payload.val_ratio,
        "samples": len(lines),
        "train": train,
        "val": val,
        "classes": classes,
        "dropped": dropped,
    }
    storage = get_storage(request)
    bucket = settings.s3_bucket_dataset
    manifest = "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines).encode()
    await run_in_threadpool(
        storage.put_bytes, bucket, manifest_key, manifest, "application/x-ndjson"
    )
    await run_in_threadpool(
        storage.put_bytes,
        bucket,
        summary_key,
        json.dumps(summary, ensure_ascii=False, indent=2).encode(),
        "application/json",
    )

    included = {line["review_id"] for line in lines}
    new_samples = 0
    for r in reviews:
        if str(r.id) in included and r.status == ReviewStatus.validated:
            r.status = ReviewStatus.exported
            r.dataset_version = version
            new_samples += 1
    await session.commit()
    log.info(
        "dataset_version_built",
        dataset_version=version,
        samples=len(lines),
        new_samples=new_samples,
        classes=classes,
        dropped=dropped,
    )
    return DatasetBuildResult(
        dataset_version=version,
        bucket=bucket,
        manifest_key=manifest_key,
        summary_key=summary_key,
        samples=len(lines),
        new_samples=new_samples,
        train=train,
        val=val,
        classes=classes,
        dropped=dropped,
    )
