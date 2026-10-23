"""Tableau de bord : agrégats sur les passages de la période, dans le périmètre de l'utilisateur."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import case, func, select

from app.api.deps import CurrentUserDep, SessionDep
from app.db.models.mismatch_review import MismatchReview, ReviewStatus
from app.db.models.passage import Decision, Passage, PassageStatus
from app.schemas.dashboard import BrandCount, DashboardSummary, HourlyPoint
from app.services.sites import get_site_in_scope, scope_filter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def summary(
    current: CurrentUserDep,
    session: SessionDep,
    site_id: uuid.UUID | None = None,
    hours: Annotated[int, Query(ge=1, le=24 * 90)] = 24,
) -> DashboardSummary:
    since = datetime.now(UTC) - timedelta(hours=hours)
    base = scope_filter(select(Passage), Passage, current).where(Passage.received_at >= since)
    reviews = scope_filter(select(MismatchReview), MismatchReview, current)
    if site_id is not None:
        site = await get_site_in_scope(session, current, site_id)
        base = base.where(Passage.site_id == site.id)
        reviews = reviews.where(MismatchReview.site_id == site.id)
    passages = base.subquery()

    totals = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(
                    func.sum(case((passages.c.decision == Decision.allowed, 1), else_=0)), 0
                ),
                func.coalesce(func.sum(case((passages.c.is_mismatch.is_(True), 1), else_=0)), 0),
                func.coalesce(
                    func.sum(case((passages.c.status != PassageStatus.ok, 1), else_=0)), 0
                ),
                func.avg(passages.c.latency_ms),
                func.percentile_cont(0.95).within_group(passages.c.latency_ms),
            ).select_from(passages)
        )
    ).one()
    count, allowed, mismatches, failed, latency_avg, latency_p95 = totals

    pending = await session.scalar(
        select(func.count()).select_from(
            reviews.where(MismatchReview.status == ReviewStatus.pending).subquery()
        )
    )

    brand_rows = (
        await session.execute(
            select(passages.c.brand_pred, func.count())
            .where(passages.c.brand_pred.is_not(None))
            .group_by(passages.c.brand_pred)
            .order_by(func.count().desc())
            .limit(8)
        )
    ).all()

    hour = func.date_trunc("hour", passages.c.received_at)
    hourly_rows = (
        await session.execute(
            select(
                hour,
                func.sum(case((passages.c.decision == Decision.allowed, 1), else_=0)),
                func.sum(case((passages.c.decision == Decision.denied, 1), else_=0)),
            )
            .group_by(hour)
            .order_by(hour)
        )
    ).all()

    return DashboardSummary(
        period_hours=hours,
        passages=int(count),
        allowed=int(allowed),
        denied=int(count) - int(allowed),
        mismatches=int(mismatches),
        failed=int(failed),
        pending_reviews=int(pending or 0),
        latency_avg_ms=round(float(latency_avg), 1) if latency_avg is not None else None,
        latency_p95_ms=round(float(latency_p95), 1) if latency_p95 is not None else None,
        top_brands=[BrandCount(brand=b, count=int(n)) for b, n in brand_rows],
        hourly=[HourlyPoint(hour=h, allowed=int(a), denied=int(d)) for h, a, d in hourly_rows],
    )
