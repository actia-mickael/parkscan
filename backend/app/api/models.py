"""Modèles servis : provenance et versions du service ML, rechargement à chaud (administrateur)."""

import httpx
from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import AdminDep, CurrentUserDep, get_ml_client
from app.core.logging import get_logger
from app.schemas.models import ServedModels
from app.services.ml_client import MlUnavailableError

router = APIRouter(prefix="/models", tags=["models"])
log = get_logger(__name__)


@router.get("", response_model=ServedModels)
async def served_models(request: Request, _current: CurrentUserDep) -> ServedModels:
    try:
        payload = await get_ml_client(request).models()
    except (MlUnavailableError, httpx.HTTPError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Service ML indisponible") from exc
    return ServedModels.model_validate(payload)


@router.post("/reload", response_model=ServedModels)
async def reload_models(request: Request, current: AdminDep) -> ServedModels:
    """Re-résout les modèles (alias MLflow ou poids locaux) et les remplace sans interruption."""
    try:
        payload = await get_ml_client(request).reload()
    except (MlUnavailableError, httpx.HTTPError) as exc:
        log.warning("models_reload_failed", error=str(exc) or type(exc).__name__)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Rechargement impossible : service ML indisponible ou modèles introuvables",
        ) from exc
    log.info("models_reloaded", user_id=str(current.user.id))
    return ServedModels.model_validate(payload)


# --- Versions et promotions (alimentées par Airflow, lues par le back-office) -------------------

from datetime import UTC, datetime  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.api.deps import InternalDep, SessionDep  # noqa: E402
from app.db.models.model_version import (  # noqa: E402
    ModelPromotion,
    ModelVersion,
    ModelVersionStatus,
    PromotionDecision,
)
from app.schemas.models import (  # noqa: E402
    ModelVersionCreate,
    ModelVersionRead,
    PromotionCreate,
    PromotionRead,
)


async def _get_or_create_version(
    session: SessionDep, name: str, version: int, payload: ModelVersionCreate | None = None
) -> ModelVersion:
    row = await session.scalar(
        select(ModelVersion).where(ModelVersion.name == name, ModelVersion.version == version)
    )
    if row is None:
        row = ModelVersion(name=name, version=version, status=ModelVersionStatus.candidate)
        session.add(row)
        await session.flush()  # identifiant généré par la base, requis par la décision
    if payload is not None:
        for field in (
            "run_id",
            "source",
            "dataset_version",
            "metrics",
            "baseline_metrics",
            "labels_count",
        ):
            value = getattr(payload, field)
            if value is not None:
                setattr(row, field, value)
    return row


@router.get("/versions", response_model=list[ModelVersionRead])
async def list_versions(_current: CurrentUserDep, session: SessionDep) -> list[ModelVersion]:
    rows = await session.scalars(
        select(ModelVersion)
        .order_by(ModelVersion.created_at.desc(), ModelVersion.version.desc())
        .limit(100)
    )
    return list(rows)


@router.post("/versions", response_model=ModelVersionRead, status_code=status.HTTP_201_CREATED)
async def register_version(
    payload: ModelVersionCreate, _: InternalDep, session: SessionDep
) -> ModelVersion:
    """Déclare (ou complète) une version produite par l'entraînement ; statut « candidat »."""
    row = await _get_or_create_version(session, payload.name, payload.version, payload)
    await session.commit()
    await session.refresh(row)
    log.info("model_version_registered", name=row.name, version=row.version, status=row.status)
    return row


def _promotion_read(promotion: ModelPromotion, version: ModelVersion) -> PromotionRead:
    return PromotionRead(
        id=promotion.id,
        model_version_id=version.id,
        name=version.name,
        version=version.version,
        decision=promotion.decision,
        reason=promotion.reason,
        candidate_metrics=promotion.candidate_metrics,
        baseline_metrics=promotion.baseline_metrics,
        previous_version=promotion.previous_version,
        decided_by=promotion.decided_by,
        created_at=promotion.created_at,
    )


@router.get("/promotions", response_model=list[PromotionRead])
async def list_promotions(_current: CurrentUserDep, session: SessionDep) -> list[PromotionRead]:
    rows = (
        await session.execute(
            select(ModelPromotion, ModelVersion)
            .join(ModelVersion, ModelVersion.id == ModelPromotion.model_version_id)
            .order_by(ModelPromotion.created_at.desc(), ModelVersion.version.desc())
            .limit(100)
        )
    ).all()
    return [_promotion_read(p, v) for p, v in rows]


@router.post("/promotions", response_model=PromotionRead, status_code=status.HTTP_201_CREATED)
async def record_promotion(
    payload: PromotionCreate, _: InternalDep, session: SessionDep
) -> PromotionRead:
    """Persiste la décision : promue (l'ancienne production devient « précédente ») ou rejetée."""
    version = await _get_or_create_version(session, payload.name, payload.version)
    previous_version: int | None = None
    if payload.decision == PromotionDecision.promoted:
        others = await session.scalars(
            select(ModelVersion).where(
                ModelVersion.name == payload.name,
                ModelVersion.id != version.id,
                ModelVersion.status.in_(
                    [ModelVersionStatus.production, ModelVersionStatus.previous]
                ),
            )
        )
        for other in others:
            if other.status == ModelVersionStatus.production:
                previous_version = other.version
                other.status = ModelVersionStatus.previous
            else:
                other.status = ModelVersionStatus.archived
        version.status = ModelVersionStatus.production
        version.promoted_at = datetime.now(UTC)
    else:
        version.status = ModelVersionStatus.rejected
    if payload.candidate_metrics is not None and version.metrics is None:
        version.metrics = payload.candidate_metrics
    if payload.baseline_metrics is not None and version.baseline_metrics is None:
        version.baseline_metrics = payload.baseline_metrics

    promotion = ModelPromotion(
        model_version_id=version.id,
        decision=payload.decision,
        reason=payload.reason,
        candidate_metrics=payload.candidate_metrics,
        baseline_metrics=payload.baseline_metrics,
        previous_version=previous_version,
        decided_by=payload.decided_by,
    )
    session.add(promotion)
    await session.commit()
    await session.refresh(promotion)
    await session.refresh(version)
    log.info(
        "model_promotion_recorded",
        name=version.name,
        version=version.version,
        decision=payload.decision,
        previous_version=previous_version,
    )
    return _promotion_read(promotion, version)
