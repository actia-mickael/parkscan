"""File de validation des écarts de marque : liste, statistiques, validation, rejet."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app.api.deps import CurrentUserDep, SessionDep, get_storage
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.slug import slugify
from app.db.models.mismatch_review import MismatchReview, ReviewOutcome, ReviewStatus
from app.db.models.passage import Passage
from app.db.models.tenant import Tenant
from app.db.models.vehicle import Vehicle
from app.schemas.common import Page
from app.schemas.mismatch import MismatchRead, MismatchStats, RejectRequest, ValidateRequest
from app.services.brands import ensure_brand
from app.services.effective_settings import resolve
from app.services.images import blur_region_jpeg, plate_rect_in_vehicle
from app.services.sites import get_site_in_scope, scope_filter
from app.services.storage import Storage

router = APIRouter(prefix="/mismatches", tags=["mismatches"])
log = get_logger(__name__)


def copy_to_dataset(
    storage: Storage,
    src_bucket: str,
    src_key: str,
    dst_bucket: str,
    dst_key: str,
    plate_rect: list[int] | None = None,
) -> None:
    """Copie le crop véhicule vers le jeu étiqueté, plaque floutée (ADR-011) : le jeu
    d'entraînement ne contient aucune donnée identifiante. Sans zone de plaque connue, copie telle
    quelle."""
    try:
        if plate_rect is None:
            storage.copy(src_bucket, src_key, dst_bucket, dst_key)
        else:
            data = storage.get_bytes(src_bucket, src_key)
            storage.put_bytes(dst_bucket, dst_key, blur_region_jpeg(data, plate_rect))
    except Exception:
        log.exception("dataset_copy_failed", key=dst_key)


async def _get_review(
    session: SessionDep, current: CurrentUserDep, review_id: uuid.UUID
) -> MismatchReview:
    review = await session.get(MismatchReview, review_id)
    if (
        review is None
        or review.tenant_id != current.tenant_id
        or not current.can_access_site(review.site_id)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Écart introuvable")
    if review.status != ReviewStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cet écart a déjà été traité")
    return review


def _read(review: MismatchReview, passage: Passage | None) -> MismatchRead:
    item = MismatchRead.model_validate(review)
    if passage is not None:
        item.plate_norm = passage.plate_norm
        item.received_at = passage.received_at
    return item


@router.get("", response_model=Page[MismatchRead])
async def list_mismatches(
    current: CurrentUserDep,
    session: SessionDep,
    review_status: Annotated[ReviewStatus | None, Query(alias="status")] = ReviewStatus.pending,
    site_id: uuid.UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[MismatchRead]:
    stmt = scope_filter(select(MismatchReview, Passage), MismatchReview, current).join(
        Passage, Passage.id == MismatchReview.passage_id
    )
    if review_status is not None:
        stmt = stmt.where(MismatchReview.status == review_status)
    if site_id is not None:
        site = await get_site_in_scope(session, current, site_id)
        stmt = stmt.where(MismatchReview.site_id == site.id)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        await session.execute(
            stmt.order_by(MismatchReview.created_at.desc()).offset((page - 1) * size).limit(size)
        )
    ).all()
    return Page(items=[_read(r, p) for r, p in rows], total=total, page=page, size=size)


@router.get("/stats", response_model=MismatchStats)
async def mismatch_stats(current: CurrentUserDep, session: SessionDep) -> MismatchStats:
    base = scope_filter(select(MismatchReview.status, func.count()), MismatchReview, current)
    counts = dict((await session.execute(base.group_by(MismatchReview.status))).all())
    by_brand_rows = (
        await session.execute(
            scope_filter(select(MismatchReview.final_brand, func.count()), MismatchReview, current)
            .where(MismatchReview.status.in_([ReviewStatus.validated, ReviewStatus.exported]))
            .group_by(MismatchReview.final_brand)
        )
    ).all()
    tenant = await session.get(Tenant, current.tenant_id)
    settings = resolve(tenant.settings if tenant else None, None)
    validated = int(counts.get(ReviewStatus.validated, 0))
    return MismatchStats(
        pending=int(counts.get(ReviewStatus.pending, 0)),
        validated=validated,
        rejected=int(counts.get(ReviewStatus.rejected, 0)),
        exported=int(counts.get(ReviewStatus.exported, 0)),
        validated_by_brand={brand or "?": int(n) for brand, n in by_brand_rows},
        min_dataset_size=settings.min_dataset_size,
        ready_for_retraining=validated >= settings.min_dataset_size,
    )


@router.post("/{review_id}/validate", response_model=MismatchRead)
async def validate_mismatch(
    request: Request,
    review_id: uuid.UUID,
    payload: ValidateRequest,
    current: CurrentUserDep,
    session: SessionDep,
    background: BackgroundTasks,
) -> MismatchRead:
    review = await _get_review(session, current, review_id)
    if payload.outcome == "predicted_correct":
        final_brand = review.predicted_brand
    elif payload.outcome == "declared_correct":
        if not review.declared_brand:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aucune marque déclarée à confirmer")
        final_brand = review.declared_brand
    else:
        if not payload.final_brand:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Marque à préciser pour l'issue « autre »"
            )
        final_brand = slugify(payload.final_brand, max_length=40, fallback="autre")
    await ensure_brand(session, final_brand)

    review.status = ReviewStatus.validated
    review.outcome = ReviewOutcome(payload.outcome)
    review.final_brand = final_brand
    review.reviewer_id = current.user.id
    review.reviewed_at = datetime.now(UTC)
    review.comment = payload.comment

    # La marque confirmée devient la marque déclarée du véhicule, sauf refus explicite.
    if payload.update_vehicle and review.vehicle_id and payload.outcome != "declared_correct":
        vehicle = await session.get(Vehicle, review.vehicle_id)
        if vehicle is not None:
            vehicle.declared_brand = final_brand

    settings = get_settings()
    passage = await session.get(Passage, review.passage_id)
    if review.source_crop_key:
        review.dataset_key = f"labeled/{final_brand}/{review.id}.jpg"
        background.add_task(
            copy_to_dataset,
            get_storage(request),
            settings.s3_bucket_captures,
            review.source_crop_key,
            settings.s3_bucket_dataset,
            review.dataset_key,
            plate_rect_in_vehicle(passage.plate_bbox, passage.vehicle_bbox) if passage else None,
        )
    await session.commit()
    await session.refresh(review)
    return _read(review, passage)


@router.post("/{review_id}/reject", response_model=MismatchRead)
async def reject_mismatch(
    review_id: uuid.UUID, payload: RejectRequest, current: CurrentUserDep, session: SessionDep
) -> MismatchRead:
    review = await _get_review(session, current, review_id)
    review.status = ReviewStatus.rejected
    review.outcome = ReviewOutcome.rejected
    review.reviewer_id = current.user.id
    review.reviewed_at = datetime.now(UTC)
    review.comment = payload.comment
    await session.commit()
    await session.refresh(review)
    passage = await session.get(Passage, review.passage_id)
    return _read(review, passage)
