"""Rétention : purge des images, plaques hachées, écarts en attente rejetés ; floutage de la plaque
dans les copies du jeu d'entraînement."""

import uuid
from datetime import UTC, datetime, timedelta
from io import BytesIO

from httpx import AsyncClient
from PIL import Image, ImageStat
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Decision, MismatchReview, Passage, PassageStatus, ReviewStatus, Site, User
from tests.conftest import auth_headers
from tests.fakes import MemoryStorage

INTERNAL = {"X-Internal-Token": get_settings().internal_token}
BUCKET = get_settings().s3_bucket_captures


async def make_passage(
    session: AsyncSession,
    site: Site,
    storage: MemoryStorage,
    *,
    age_days: int,
    plate: str = "AB-123-CD",
) -> Passage:
    passage_id = uuid.uuid4()
    prefix = f"{site.tenant_id}/{site.id}/test/{passage_id}"
    passage = Passage(
        id=passage_id,
        tenant_id=site.tenant_id,
        site_id=site.id,
        client_request_id=uuid.uuid4().hex,
        received_at=datetime.now(UTC) - timedelta(days=age_days),
        status=PassageStatus.ok,
        decision=Decision.allowed,
        decision_reason="whitelist_match",
        plate_text=plate,
        plate_norm=plate.replace("-", ""),
        plate_bbox=[60, 30, 120, 60],
        vehicle_bbox=[0, 0, 200, 100],
        image_key=f"{prefix}/full.jpg",
        plate_crop_key=f"{prefix}/plate.jpg",
        vehicle_crop_key=f"{prefix}/vehicle.jpg",
        raw_result={"plates": [{"text": plate}]},
    )
    for key in (passage.image_key, passage.plate_crop_key, passage.vehicle_crop_key):
        storage.objects[(BUCKET, key)] = b"jpeg"
    session.add(passage)
    await session.commit()
    await session.refresh(passage)
    return passage


async def test_retention_requires_internal_token(client: AsyncClient, agent: User) -> None:
    assert (await client.post("/api/v1/retention/run")).status_code == 401
    assert (
        await client.post("/api/v1/retention/run", headers=auth_headers(agent))
    ).status_code == 401


async def test_retention_purges_old_passages_only(
    client: AsyncClient, db_session: AsyncSession, site: Site, storage: MemoryStorage, agent: User
) -> None:
    old = await make_passage(db_session, site, storage, age_days=40)
    recent = await make_passage(db_session, site, storage, age_days=2, plate="EF-456-GH")
    review = MismatchReview(
        tenant_id=site.tenant_id,
        site_id=site.id,
        passage_id=old.id,
        predicted_brand="renault",
        predicted_conf=0.9,
        declared_brand="dacia",
        source_crop_key=old.vehicle_crop_key,
    )
    db_session.add(review)
    await db_session.commit()

    preview = (await client.post("/api/v1/retention/run?dry_run=true", headers=INTERNAL)).json()
    assert preview["dry_run"] is True and preview["sites"].get(site.slug) == 1

    response = await client.post("/api/v1/retention/run", headers=INTERNAL)
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["sites"][site.slug] == 1
    assert report["images_deleted"] >= 3 and report["passages_anonymized"] >= 1
    assert report["reviews_rejected"] >= 1 and report["errors"] == 0

    await db_session.refresh(old)
    await db_session.refresh(recent)
    await db_session.refresh(review)
    assert old.image_key is None and old.plate_crop_key is None and old.vehicle_crop_key is None
    assert old.plate_text.startswith("anon:") and old.plate_norm != "AB123CD"
    assert len(old.plate_norm) == 12 and old.raw_result is None
    assert old.anonymized_at is not None and old.images_purged_at is not None
    assert all(
        (BUCKET, k) not in storage.objects
        for k in (f"{site.tenant_id}/{site.id}/test/{old.id}/full.jpg",)
    )
    assert review.status == ReviewStatus.rejected
    assert (
        recent.plate_text == "EF-456-GH"
        and recent.image_key
        and (BUCKET, recent.image_key) in storage.objects
    )

    # Vu par un agent : la plaque hachée, pas d'image
    detail = (await client.get(f"/api/v1/passages/{old.id}", headers=auth_headers(agent))).json()
    assert detail["plate_text"].startswith("anon:") and detail["anonymized_at"]
    assert (
        await client.get(f"/api/v1/passages/{old.id}/image", headers=auth_headers(agent))
    ).status_code == 404

    # Rejouer ne retraite rien : idempotent
    again = (await client.post("/api/v1/retention/run", headers=INTERNAL)).json()
    assert again["sites"].get(site.slug, 0) == 0


def _plate_image() -> bytes:
    image = Image.new("RGB", (200, 100), (90, 90, 90))
    for x in range(60, 120, 6):  # rayures contrastées dans la zone de la plaque
        image.paste((255, 255, 255), (x, 30, x + 3, 60))
    out = BytesIO()
    image.save(out, format="JPEG", quality=95)
    return out.getvalue()


def _region_std(data: bytes) -> float:
    with Image.open(BytesIO(data)) as image:
        return ImageStat.Stat(image.convert("L").crop((60, 30, 120, 60))).stddev[0]


async def test_validation_blurs_plate_in_dataset_copy(
    client: AsyncClient, db_session: AsyncSession, site: Site, storage: MemoryStorage, manager: User
) -> None:
    passage = await make_passage(db_session, site, storage, age_days=0)
    source = _plate_image()
    storage.objects[(BUCKET, passage.vehicle_crop_key)] = source
    review = MismatchReview(
        tenant_id=site.tenant_id,
        site_id=site.id,
        passage_id=passage.id,
        predicted_brand="renault",
        predicted_conf=0.9,
        declared_brand="dacia",
        source_crop_key=passage.vehicle_crop_key,
    )
    db_session.add(review)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/mismatches/{review.id}/validate",
        json={"outcome": "declared_correct"},
        headers=auth_headers(manager),
    )
    assert response.status_code == 200, response.text
    dataset_key = response.json()["dataset_key"]
    copied = storage.objects[(get_settings().s3_bucket_dataset, dataset_key)]
    assert copied != source
    assert _region_std(copied) < _region_std(source) / 3, "la zone de la plaque doit être floutée"
