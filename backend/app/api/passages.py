"""Passages : historique filtrable, détail, image présignée."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app.api.deps import CurrentUserDep, SessionDep, get_storage
from app.core.config import get_settings
from app.core.plates import normalize_plate
from app.db.models.passage import Decision, Passage, PassageStatus
from app.schemas.common import Page
from app.schemas.passage import PassageDetail, PassageRead, PresignedImage
from app.services.sites import get_site_in_scope, scope_filter

router = APIRouter(prefix="/passages", tags=["passages"])


async def get_passage_in_scope(
    session: SessionDep, current: CurrentUserDep, passage_id: uuid.UUID
) -> Passage:
    passage = await session.get(Passage, passage_id)
    if (
        passage is None
        or passage.tenant_id != current.tenant_id
        or not current.can_access_site(passage.site_id)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Passage introuvable")
    return passage


@router.get("", response_model=Page[PassageRead])
async def list_passages(
    current: CurrentUserDep,
    session: SessionDep,
    site_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    decision: Decision | None = None,
    passage_status: Annotated[PassageStatus | None, Query(alias="status")] = None,
    plate: Annotated[str | None, Query(max_length=20)] = None,
    is_mismatch: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[PassageRead]:
    stmt = scope_filter(select(Passage), Passage, current)
    if site_id is not None:
        site = await get_site_in_scope(session, current, site_id)
        stmt = stmt.where(Passage.site_id == site.id)
    if since is not None:
        stmt = stmt.where(Passage.received_at >= since)
    if until is not None:
        stmt = stmt.where(Passage.received_at <= until)
    if decision is not None:
        stmt = stmt.where(Passage.decision == decision)
    if passage_status is not None:
        stmt = stmt.where(Passage.status == passage_status)
    if plate:
        stmt = stmt.where(Passage.plate_norm.contains(normalize_plate(plate)))
    if is_mismatch is not None:
        stmt = stmt.where(Passage.is_mismatch.is_(is_mismatch))

    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await session.scalars(
        stmt.order_by(Passage.received_at.desc()).offset((page - 1) * size).limit(size)
    )
    return Page(
        items=[PassageRead.model_validate(p) for p in rows], total=total, page=page, size=size
    )


@router.get("/{passage_id}", response_model=PassageDetail)
async def read_passage(
    passage_id: uuid.UUID, current: CurrentUserDep, session: SessionDep
) -> Passage:
    return await get_passage_in_scope(session, current, passage_id)


@router.get("/{passage_id}/image", response_model=PresignedImage)
async def passage_image(
    request: Request,
    passage_id: uuid.UUID,
    current: CurrentUserDep,
    session: SessionDep,
    kind: Literal["full", "plate", "vehicle"] = "full",
) -> PresignedImage:
    passage = await get_passage_in_scope(session, current, passage_id)
    key = {
        "full": passage.image_key,
        "plate": passage.plate_crop_key,
        "vehicle": passage.vehicle_crop_key,
    }[kind]
    if not key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pas d'image de ce type pour ce passage")
    settings = get_settings()
    url = get_storage(request).presigned_get_url(
        settings.s3_bucket_captures, key, settings.presign_expires_seconds
    )
    return PresignedImage(url=url, expires_in=settings.presign_expires_seconds, kind=kind)
