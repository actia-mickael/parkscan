"""Ingestion de captures : décision, unicité du passage, idempotence, écart de marque, dégradation."""

import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Brand, MismatchReview, Passage, Site
from tests.conftest import make_api_key, make_resident, make_vehicle
from tests.fakes import FakeMlClient, MemoryStorage, jpeg_bytes, ml_result

JPEG = jpeg_bytes()


async def _capture(
    client: AsyncClient, secret: str, request_id: str | None = None, **form: str
) -> object:
    return await client.post(
        "/api/v1/ingest/capture",
        headers={"X-Api-Key": secret},
        files={"image": ("capture.jpg", JPEG, "image/jpeg")},
        data={"client_request_id": request_id or uuid.uuid4().hex, **form},
    )


async def _count(session: AsyncSession, model: type, site_id: object) -> int:
    # Limité au site du test : la base de développement peut contenir de vrais passages.
    stmt = select(func.count()).select_from(model).where(model.site_id == site_id)
    return int(await session.scalar(stmt) or 0)


async def test_known_plate_is_allowed_and_stored_once(
    client: AsyncClient, db_session: AsyncSession, site: Site, storage: MemoryStorage
) -> None:
    resident = await make_resident(db_session, site)
    vehicle = await make_vehicle(db_session, resident, "AB-123-CD")
    _, secret = await make_api_key(db_session, site)

    response = await _capture(client, secret)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["decision"] == "allowed"
    assert body["reason"] == "whitelist_match"
    assert body["plate_norm"] == "AB123CD"
    assert body["is_mismatch"] is False
    assert body["duplicate"] is False

    passage = await db_session.get(Passage, uuid.UUID(body["passage_id"]))
    assert passage is not None
    assert passage.vehicle_id == vehicle.id
    assert passage.status == "ok"
    assert passage.image_key and passage.image_key.endswith("/full.jpg")
    assert await _count(db_session, Passage, site.id) == 1
    # Les trois images ont été envoyées au stockage après la réponse.
    assert len(storage.objects) == 3


async def test_unknown_disabled_and_no_plate(
    client: AsyncClient, db_session: AsyncSession, site: Site, fake_ml: FakeMlClient
) -> None:
    resident = await make_resident(db_session, site)
    await make_vehicle(db_session, resident, "EF-456-GH", access_enabled=False)
    _, secret = await make_api_key(db_session, site)

    unknown = (await _capture(client, secret)).json()
    assert (unknown["decision"], unknown["reason"]) == ("denied", "unknown_plate")

    fake_ml.result = ml_result(plate="EF-456-GH")
    disabled = (await _capture(client, secret)).json()
    assert (disabled["decision"], disabled["reason"]) == ("denied", "access_disabled")

    fake_ml.result = ml_result(plate=None)
    nothing = (await _capture(client, secret)).json()
    assert (nothing["status"], nothing["decision"], nothing["reason"]) == (
        "no_plate",
        "denied",
        "no_plate_read",
    )

    fake_ml.result = ml_result(plate="EF-456-GH", ocr_conf=0.3)
    weak = (await _capture(client, secret)).json()
    assert (weak["status"], weak["reason"]) == ("low_ocr_conf", "low_ocr_conf")

    assert await _count(db_session, Passage, site.id) == 4


async def test_same_request_id_is_idempotent(
    client: AsyncClient, db_session: AsyncSession, site: Site, fake_ml: FakeMlClient
) -> None:
    _, secret = await make_api_key(db_session, site)
    first = (await _capture(client, secret, request_id="req-0001-abcd")).json()
    again = (await _capture(client, secret, request_id="req-0001-abcd")).json()
    assert again["passage_id"] == first["passage_id"]
    assert again["duplicate"] is True
    assert fake_ml.calls == 1
    assert await _count(db_session, Passage, site.id) == 1


async def test_ml_unavailable_denies_and_records(
    client: AsyncClient, db_session: AsyncSession, site: Site, fake_ml: FakeMlClient
) -> None:
    _, secret = await make_api_key(db_session, site)
    fake_ml.unavailable = True
    response = await _capture(client, secret)
    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["decision"], body["reason"]) == (
        "ml_error",
        "denied",
        "ml_unavailable",
    )
    assert await _count(db_session, Passage, site.id) == 1


async def test_brand_mismatch_creates_pending_review(
    client: AsyncClient, db_session: AsyncSession, site: Site, fake_ml: FakeMlClient
) -> None:
    for slug, aliases in (("renault", []), ("volkswagen", ["vw"])):
        if await db_session.get(Brand, slug) is None:
            db_session.add(Brand(slug=slug, display_name=slug.title(), aliases=aliases))
    await db_session.commit()
    resident = await make_resident(db_session, site)
    vehicle = await make_vehicle(db_session, resident, "AB-123-CD")
    vehicle.declared_brand = "volkswagen"
    await db_session.commit()
    _, secret = await make_api_key(db_session, site)

    # Prédiction "renault" sûre contre une déclaration "volkswagen" : écart.
    body = (await _capture(client, secret)).json()
    assert body["decision"] == "allowed"
    assert body["is_mismatch"] is True
    review = await db_session.scalar(
        select(MismatchReview).where(MismatchReview.site_id == site.id)
    )
    assert review is not None and review.status == "pending"
    assert (review.predicted_brand, review.declared_brand) == ("renault", "volkswagen")

    # Alias : "VW" prédit = "volkswagen" déclaré, pas d'écart. Confiance faible : pas d'écart non plus.
    fake_ml.result = ml_result(brand="VW", brand_conf=0.95)
    assert (await _capture(client, secret)).json()["is_mismatch"] is False
    fake_ml.result = ml_result(brand="renault", brand_conf=0.4)
    assert (await _capture(client, secret)).json()["is_mismatch"] is False
    assert await _count(db_session, MismatchReview, site.id) == 1


async def test_rate_limit(client: AsyncClient, db_session: AsyncSession, site: Site) -> None:
    from app.core.ratelimit import TokenBucketLimiter
    from app.main import app

    app.state.rate_limiter = TokenBucketLimiter(rate_per_minute=2, burst=2)
    _, secret = await make_api_key(db_session, site)
    assert (await _capture(client, secret)).status_code == 200
    assert (await _capture(client, secret)).status_code == 200
    assert (await _capture(client, secret)).status_code == 429
