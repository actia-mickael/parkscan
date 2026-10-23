"""Rétention (ADR-011) : au-delà de la durée de conservation effective (site > locataire > défaut),
les images d'un passage sont supprimées du stockage et sa plaque remplacée par un haché à clé
(HMAC-SHA256 tronqué) : les statistiques restent exploitables, l'identification n'est plus possible.
Les écarts encore en attente sur ces passages sont rejetés (l'image n'existe plus)."""

import hashlib
import hmac
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.models.mismatch_review import MismatchReview, ReviewOutcome, ReviewStatus
from app.db.models.passage import Passage
from app.db.models.site import Site
from app.db.models.tenant import Tenant
from app.services.effective_settings import resolve
from app.services.storage import Storage

log = get_logger(__name__)
BATCH = 200
PURGE_COMMENT = "image supprimée par la rétention"


@dataclass(slots=True)
class RetentionReport:
    dry_run: bool = False
    scanned: int = 0
    images_deleted: int = 0
    passages_anonymized: int = 0
    reviews_rejected: int = 0
    errors: int = 0
    sites: dict[str, int] = field(default_factory=dict)  # slug du site → passages traités

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def plate_digest(plate_norm: str, secret: str) -> str:
    """Haché à clé, tronqué à 12 caractères : stable (regroupements possibles), non réversible."""
    digest = hmac.new(secret.encode("utf-8"), plate_norm.upper().encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()[:12].upper()


def _due(site_id: Any, cutoff: datetime):
    """Passages du site plus vieux que la limite et pas encore entièrement traités."""
    return select(Passage).where(
        Passage.site_id == site_id,
        Passage.received_at < cutoff,
        or_(
            Passage.anonymized_at.is_(None),
            Passage.image_key.is_not(None),
            Passage.plate_crop_key.is_not(None),
            Passage.vehicle_crop_key.is_not(None),
        ),
    )


async def _purge_images(
    storage: Storage, bucket: str, passage: Passage, now: datetime, report: RetentionReport
) -> None:
    for attribute in ("image_key", "plate_crop_key", "vehicle_crop_key"):
        key = getattr(passage, attribute)
        if not key:
            continue
        try:
            await run_in_threadpool(storage.delete, bucket, key)
        except Exception:
            report.errors += 1
            log.exception("retention_delete_failed", key=key)
            continue  # la clé est conservée : nouvelle tentative au prochain passage
        setattr(passage, attribute, None)
        report.images_deleted += 1
    if not (passage.image_key or passage.plate_crop_key or passage.vehicle_crop_key):
        passage.images_purged_at = passage.images_purged_at or now


def _anonymize(passage: Passage, secret: str, now: datetime) -> None:
    if passage.plate_norm:
        digest = plate_digest(passage.plate_norm, secret)
        passage.plate_text = f"anon:{digest}"
        passage.plate_norm = digest
    passage.raw_result = None  # contient le texte lu par l'OCR
    passage.anonymized_at = now


async def run_retention(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    *,
    now: datetime | None = None,
    dry_run: bool = False,
) -> RetentionReport:
    now = now or datetime.now(UTC)
    report = RetentionReport(dry_run=dry_run)
    secret = settings.anonymization_secret or settings.jwt_secret
    rows = (
        await session.execute(select(Site, Tenant).join(Tenant, Tenant.id == Site.tenant_id))
    ).all()
    for site, tenant in rows:
        days = resolve(tenant.settings, site.settings).retention_days
        if days <= 0:
            continue  # conservation illimitée pour ce site
        cutoff = now - timedelta(days=days)
        if dry_run:
            count = int(
                await session.scalar(
                    select(func.count()).select_from(_due(site.id, cutoff).subquery())
                )
                or 0
            )
            if count:
                report.sites[site.slug] = count
                report.scanned += count
            continue
        while True:
            passages = list(
                await session.scalars(
                    _due(site.id, cutoff).order_by(Passage.received_at).limit(BATCH)
                )
            )
            if not passages:
                break
            for passage in passages:
                report.scanned += 1
                await _purge_images(storage, settings.s3_bucket_captures, passage, now, report)
                if passage.anonymized_at is None:
                    _anonymize(passage, secret, now)
                    report.passages_anonymized += 1
                pending = await session.scalars(
                    select(MismatchReview).where(
                        MismatchReview.passage_id == passage.id,
                        MismatchReview.status == ReviewStatus.pending,
                    )
                )
                for review in pending:
                    review.status = ReviewStatus.rejected
                    review.outcome = ReviewOutcome.rejected
                    review.reviewed_at = now
                    review.comment = PURGE_COMMENT
                    report.reviews_rejected += 1
            report.sites[site.slug] = report.sites.get(site.slug, 0) + len(passages)
            await session.commit()
            if len(passages) < BATCH:
                break
    log.info("retention_done", **report.as_dict())
    return report
