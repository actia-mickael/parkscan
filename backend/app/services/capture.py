"""Traitement d'une capture : appel ML, décision, écart de marque, persistance, envoi des images.

Le chemin critique (jusqu'à la réponse à l'agent) ne contient que : une lecture de la base, l'appel
ML, une lecture de la liste blanche, une insertion. Les envois vers le stockage se font après la
réponse.
"""

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ApiKeyContext
from app.core.brands import canonical, is_mismatch
from app.core.config import Settings
from app.core.logging import get_logger
from app.db.models.mismatch_review import MismatchReview, ReviewStatus
from app.db.models.passage import Decision, Passage, PassageStatus
from app.db.models.tenant import Tenant
from app.schemas.ml import MlInferResult
from app.services.access_decision import decide
from app.services.brands import load_alias_map
from app.services.effective_settings import EffectiveSettings, resolve
from app.services.images import crop_jpeg
from app.services.ml_client import MlClient, MlUnavailableError
from app.services.storage import Storage

log = get_logger(__name__)


@dataclass(slots=True)
class CaptureInput:
    ctx: ApiKeyContext
    image: bytes
    client_request_id: str
    captured_at: datetime | None
    run_brand: bool


def storage_keys(
    tenant_id: uuid.UUID, site_id: uuid.UUID, passage_id: uuid.UUID, when: datetime
) -> dict[str, str]:
    prefix = f"{tenant_id}/{site_id}/{when:%Y/%m/%d}/{passage_id}"
    return {
        "full": f"{prefix}/full.jpg",
        "plate": f"{prefix}/plate.jpg",
        "vehicle": f"{prefix}/vehicle.jpg",
    }


def upload_capture(
    storage: Storage,
    bucket: str,
    image: bytes,
    keys: dict[str, str],
    plate_bbox: list[int] | None,
    vehicle_bbox: list[int] | None,
) -> None:
    """Tâche de fond : image complète puis crops, chacun indépendamment. Une erreur est journalisée,
    jamais remontée à l'agent, et n'empêche pas l'envoi des autres fichiers."""
    jobs: list[tuple[str, list[int] | None]] = [("full", None)]
    if plate_bbox:
        jobs.append(("plate", plate_bbox))
    if vehicle_bbox:
        jobs.append(("vehicle", vehicle_bbox))
    for kind, bbox in jobs:
        try:
            data = image if bbox is None else crop_jpeg(image, bbox)
            storage.put_bytes(bucket, keys[kind], data)
        except Exception:
            log.exception("capture_upload_failed", kind=kind, key=keys[kind])


async def find_existing(
    session: AsyncSession, site_id: uuid.UUID, client_request_id: str
) -> Passage | None:
    return await session.scalar(
        select(Passage).where(
            Passage.site_id == site_id, Passage.client_request_id == client_request_id
        )
    )


async def effective_settings_for(session: AsyncSession, ctx: ApiKeyContext) -> EffectiveSettings:
    tenant = await session.get(Tenant, ctx.tenant_id)
    return resolve(tenant.settings if tenant else None, ctx.site.settings)


async def process_capture(
    session: AsyncSession,
    ml: MlClient,
    storage: Storage,
    settings: Settings,
    background: BackgroundTasks,
    data: CaptureInput,
) -> Passage:
    started = time.perf_counter()
    now = datetime.now(UTC)
    ctx = data.ctx
    thresholds = await effective_settings_for(session, ctx)
    passage_id = uuid.uuid4()
    keys = storage_keys(ctx.tenant_id, ctx.site.id, passage_id, now)

    passage = Passage(
        id=passage_id,
        tenant_id=ctx.tenant_id,
        site_id=ctx.site.id,
        api_key_id=ctx.api_key.id,
        captured_at=data.captured_at,
        client_request_id=data.client_request_id,
        image_key=keys["full"],
        status=PassageStatus.ok,
        decision=Decision.denied,
        decision_reason="unknown_plate",
    )

    try:
        result = await ml.infer(
            data.image,
            det_threshold=thresholds.detection_threshold,
            vehicle_threshold=thresholds.vehicle_threshold,
            run_branch2=data.run_brand,
        )
    except MlUnavailableError as exc:
        log.warning("ml_unavailable", error=str(exc), site_id=str(ctx.site.id))
        passage.status = PassageStatus.ml_error
        passage.decision_reason = "ml_unavailable"
        passage.latency_ms = int((time.perf_counter() - started) * 1000)
        session.add(passage)
        await session.commit()
        background.add_task(
            upload_capture, storage, settings.s3_bucket_captures, data.image, keys, None, None
        )
        return passage

    _apply_ml_result(passage, result, keys, thresholds)

    plate_norm = passage.plate_norm if passage.status == PassageStatus.ok else None
    outcome = await decide(session, ctx.site.id, plate_norm, now.date())
    passage.decision, passage.decision_reason = outcome.decision, outcome.reason
    if passage.status == PassageStatus.low_ocr_conf:
        passage.decision, passage.decision_reason = Decision.denied, "low_ocr_conf"
    elif passage.status == PassageStatus.no_plate:
        passage.decision, passage.decision_reason = Decision.denied, "no_plate_read"

    review: MismatchReview | None = None
    if outcome.vehicle is not None:
        passage.vehicle_id = outcome.vehicle.id
        passage.declared_brand_snapshot = outcome.vehicle.declared_brand
        if result.brand is not None and outcome.vehicle.declared_brand:
            alias_map = await load_alias_map(session)
            passage.is_mismatch = is_mismatch(
                result.brand.label,
                result.brand.conf,
                outcome.vehicle.declared_brand,
                thresholds.brand_threshold,
                alias_map,
            )
            if passage.is_mismatch:
                review = MismatchReview(
                    tenant_id=ctx.tenant_id,
                    site_id=ctx.site.id,
                    passage_id=passage.id,
                    vehicle_id=outcome.vehicle.id,
                    predicted_brand=canonical(result.brand.label, alias_map) or result.brand.label,
                    predicted_conf=result.brand.conf,
                    declared_brand=outcome.vehicle.declared_brand,
                    status=ReviewStatus.pending,
                    source_crop_key=passage.vehicle_crop_key,
                )

    passage.latency_ms = int((time.perf_counter() - started) * 1000)
    session.add(passage)
    await session.flush()  # le passage doit exister avant l'écart qui le référence
    if review is not None:
        session.add(review)
    await session.commit()

    background.add_task(
        upload_capture,
        storage,
        settings.s3_bucket_captures,
        data.image,
        keys,
        passage.plate_bbox,
        passage.vehicle_bbox,
    )
    log.info(
        "capture",
        site=ctx.site.slug,
        plate=passage.plate_norm,
        decision=passage.decision.value,
        reason=passage.decision_reason,
        mismatch=passage.is_mismatch,
        latency_ms=passage.latency_ms,
        ml_ms=passage.ml_latency_ms,
    )
    return passage


def _apply_ml_result(
    passage: Passage, result: MlInferResult, keys: dict[str, str], thresholds: EffectiveSettings
) -> None:
    passage.ml_latency_ms = int(result.timings_ms.get("total", 0))
    passage.model_versions = result.model_versions
    passage.conditions = result.conditions
    passage.raw_result = result.model_dump()

    if result.vehicle is not None:
        passage.vehicle_bbox = result.vehicle.bbox
        passage.vehicle_class = result.vehicle.class_name
        passage.vehicle_crop_key = keys["vehicle"]
    if result.brand is not None:
        passage.brand_pred = result.brand.label
        passage.brand_conf = result.brand.conf
        passage.brand_top3 = [list(t) for t in result.brand.top3]

    if not result.plates:
        passage.status = PassageStatus.no_plate
        return
    plate = result.plates[0]
    passage.plate_text = plate.text
    passage.plate_norm = plate.text_norm or None
    passage.ocr_conf = plate.ocr_conf
    passage.det_conf = plate.det_conf
    passage.plate_bbox = plate.bbox
    passage.plate_crop_key = keys["plate"]
    if not plate.text_norm:
        passage.status = PassageStatus.no_plate
    elif plate.ocr_conf < thresholds.ocr_threshold:
        passage.status = PassageStatus.low_ocr_conf
