"""Historique des passages, image présignée, validation et rejet des écarts."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Brand, MismatchReview, Site, User, Vehicle
from tests.conftest import auth_headers, make_api_key, make_resident, make_vehicle
from tests.fakes import FakeMlClient, MemoryStorage, ml_result
from tests.test_ingest import JPEG


async def _capture(client: AsyncClient, secret: str) -> dict:
    response = await client.post(
        "/api/v1/ingest/capture",
        headers={"X-Api-Key": secret},
        files={"image": ("capture.jpg", JPEG, "image/jpeg")},
        data={"client_request_id": uuid.uuid4().hex},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _seed_mismatch(db_session: AsyncSession, site: Site, fake_ml: FakeMlClient) -> Vehicle:
    for slug in ("renault", "peugeot"):
        if await db_session.get(Brand, slug) is None:
            db_session.add(Brand(slug=slug, display_name=slug.title()))
    resident = await make_resident(db_session, site)
    vehicle = await make_vehicle(db_session, resident, "AB-123-CD")
    vehicle.declared_brand = "peugeot"
    await db_session.commit()
    fake_ml.result = ml_result(brand="renault", brand_conf=0.9)
    return vehicle


async def test_passages_listing_filters_and_image_url(
    client: AsyncClient,
    db_session: AsyncSession,
    site: Site,
    other_site: Site,
    manager: User,
    other_admin: User,
) -> None:
    resident = await make_resident(db_session, site)
    await make_vehicle(db_session, resident, "AB-123-CD")
    _, secret = await make_api_key(db_session, site)
    allowed = await _capture(client, secret)

    listed = await client.get("/api/v1/passages", headers=auth_headers(manager))
    assert listed.status_code == 200
    assert [p["id"] for p in listed.json()["items"]] == [allowed["passage_id"]]

    only_denied = await client.get(
        "/api/v1/passages?decision=denied", headers=auth_headers(manager)
    )
    assert only_denied.json()["total"] == 0
    by_plate = await client.get("/api/v1/passages?plate=ab-123", headers=auth_headers(manager))
    assert by_plate.json()["total"] == 1

    foreign = await client.get("/api/v1/passages", headers=auth_headers(other_admin))
    assert foreign.json()["total"] == 0
    direct = await client.get(
        f"/api/v1/passages/{allowed['passage_id']}", headers=auth_headers(other_admin)
    )
    assert direct.status_code == 404

    detail = await client.get(
        f"/api/v1/passages/{allowed['passage_id']}", headers=auth_headers(manager)
    )
    assert detail.json()["raw_result"]["timings_ms"]["total"] == 250.0

    image = await client.get(
        f"/api/v1/passages/{allowed['passage_id']}/image?kind=vehicle",
        headers=auth_headers(manager),
    )
    assert image.status_code == 200
    assert image.json()["url"].startswith("http://storage.test/parkscan-captures/")


async def test_validate_predicted_updates_vehicle_and_copies_crop(
    client: AsyncClient,
    db_session: AsyncSession,
    site: Site,
    agent: User,
    fake_ml: FakeMlClient,
    storage: MemoryStorage,
) -> None:
    vehicle = await _seed_mismatch(db_session, site, fake_ml)
    _, secret = await make_api_key(db_session, site)
    capture = await _capture(client, secret)
    assert capture["is_mismatch"] is True

    queue = await client.get("/api/v1/mismatches", headers=auth_headers(agent))
    assert queue.json()["total"] == 1
    review = queue.json()["items"][0]
    assert review["plate_norm"] == "AB123CD"

    validated = await client.post(
        f"/api/v1/mismatches/{review['id']}/validate",
        json={"outcome": "predicted_correct"},
        headers=auth_headers(agent),
    )
    assert validated.status_code == 200, validated.text
    body = validated.json()
    assert body["status"] == "validated"
    assert body["final_brand"] == "renault"
    assert body["dataset_key"] == f"labeled/renault/{review['id']}.jpg"
    assert ("parkscan-dataset", body["dataset_key"]) in storage.objects

    await db_session.refresh(vehicle)
    assert vehicle.declared_brand == "renault"

    again = await client.post(
        f"/api/v1/mismatches/{review['id']}/validate",
        json={"outcome": "predicted_correct"},
        headers=auth_headers(agent),
    )
    assert again.status_code == 409

    stats = await client.get("/api/v1/mismatches/stats", headers=auth_headers(agent))
    assert stats.json()["validated"] == 1
    assert stats.json()["validated_by_brand"] == {"renault": 1}
    assert stats.json()["ready_for_retraining"] is False


async def test_reject_and_custom_brand(
    client: AsyncClient, db_session: AsyncSession, site: Site, manager: User, fake_ml: FakeMlClient
) -> None:
    await _seed_mismatch(db_session, site, fake_ml)
    _, secret = await make_api_key(db_session, site)
    first = await _capture(client, secret)
    second = await _capture(client, secret)
    reviews = {r.passage_id: r for r in await db_session.scalars(select(MismatchReview))}
    r1 = reviews[uuid.UUID(first["passage_id"])]
    r2 = reviews[uuid.UUID(second["passage_id"])]

    rejected = await client.post(
        f"/api/v1/mismatches/{r1.id}/reject",
        json={"comment": "photo floue"},
        headers=auth_headers(manager),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    custom = await client.post(
        f"/api/v1/mismatches/{r2.id}/validate",
        json={"outcome": "custom", "final_brand": "Alfa Romeo", "update_vehicle": False},
        headers=auth_headers(manager),
    )
    assert custom.status_code == 200, custom.text
    assert custom.json()["final_brand"] == "alfa-romeo"
    assert await db_session.get(Brand, "alfa-romeo") is not None
