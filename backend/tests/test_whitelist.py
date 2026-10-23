from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Site
from tests.conftest import make_api_key, make_resident, make_vehicle


async def test_whitelist_returns_active_plates_with_etag(
    client: AsyncClient, db_session: AsyncSession, site: Site, other_site: Site
) -> None:
    resident = await make_resident(db_session, site)
    await make_vehicle(db_session, resident, "AB-123-CD")
    await make_vehicle(db_session, resident, "EF-456-GH", access_enabled=False)
    foreign_resident = await make_resident(db_session, other_site)
    await make_vehicle(db_session, foreign_resident, "IJ-789-KL")
    _, secret = await make_api_key(db_session, site)

    response = await client.get("/api/v1/ingest/whitelist", headers={"X-Api-Key": secret})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["site_id"] == str(site.id)
    assert body["plates"] == ["AB123CD"]
    etag = response.headers["ETag"]
    assert body["etag"] == etag

    not_modified = await client.get(
        "/api/v1/ingest/whitelist", headers={"X-Api-Key": secret, "If-None-Match": etag}
    )
    assert not_modified.status_code == 304

    await make_vehicle(db_session, resident, "MN-012-OP")
    changed = await client.get(
        "/api/v1/ingest/whitelist", headers={"X-Api-Key": secret, "If-None-Match": etag}
    )
    assert changed.status_code == 200
    assert changed.json()["plates"] == ["AB123CD", "MN012OP"]


async def test_whitelist_rejects_missing_revoked_or_foreign_keys(
    client: AsyncClient, db_session: AsyncSession, site: Site
) -> None:
    missing = await client.get("/api/v1/ingest/whitelist")
    assert missing.status_code == 401

    wrong = await client.get("/api/v1/ingest/whitelist", headers={"X-Api-Key": "psk_nope"})
    assert wrong.status_code == 401

    api_key, secret = await make_api_key(db_session, site)
    api_key.revoked_at = datetime.now(UTC)
    await db_session.commit()
    revoked = await client.get("/api/v1/ingest/whitelist", headers={"X-Api-Key": secret})
    assert revoked.status_code == 401
