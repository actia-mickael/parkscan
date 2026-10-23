from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Site, User
from tests.conftest import auth_headers, make_api_key, make_resident, make_vehicle
from tests.fakes import FakeMlClient, ml_result
from tests.test_ingest import JPEG


async def test_dashboard_summary_counts_period(
    client: AsyncClient, db_session: AsyncSession, site: Site, manager: User, fake_ml: FakeMlClient
) -> None:
    resident = await make_resident(db_session, site)
    await make_vehicle(db_session, resident, "AB-123-CD")
    _, secret = await make_api_key(db_session, site)
    for plate in ("AB-123-CD", "ZZ-999-ZZ", None):
        fake_ml.result = ml_result(plate=plate)
        response = await client.post(
            "/api/v1/ingest/capture",
            headers={"X-Api-Key": secret},
            files={"image": ("c.jpg", JPEG, "image/jpeg")},
            data={"client_request_id": f"dash-{plate}"},
        )
        assert response.status_code == 200

    summary = await client.get(
        f"/api/v1/dashboard/summary?site_id={site.id}", headers=auth_headers(manager)
    )
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert (body["passages"], body["allowed"], body["denied"], body["failed"]) == (3, 1, 2, 1)
    assert body["top_brands"][0]["brand"] == "renault"
    assert body["latency_p95_ms"] is not None
    assert sum(p["allowed"] + p["denied"] for p in body["hourly"]) == 3
