from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Site, Tenant, User
from tests.conftest import auth_headers, make_resident, make_site


async def _create_resident(client: AsyncClient, user: User, site: Site, **extra: object) -> dict:
    payload = {"site_id": str(site.id), "last_name": "Durand", "first_name": "Camille", **extra}
    response = await client.post("/api/v1/residents", json=payload, headers=auth_headers(user))
    assert response.status_code == 201, response.text
    return response.json()


async def test_manager_creates_resident_and_vehicle_with_normalized_plate(
    client: AsyncClient, manager: User, site: Site
) -> None:
    resident = await _create_resident(client, manager, site, email="Camille@Demo.example")
    assert resident["email"] == "camille@demo.example"

    created = await client.post(
        "/api/v1/vehicles",
        json={"resident_id": resident["id"], "plate": "ab-123-cd", "declared_brand": "renault"},
        headers=auth_headers(manager),
    )
    assert created.status_code == 201, created.text
    vehicle = created.json()
    assert vehicle["plate_norm"] == "AB123CD"
    assert vehicle["plate_raw"] == "ab-123-cd"
    assert vehicle["site_id"] == str(site.id)

    found = await client.get("/api/v1/vehicles?plate=AB 123 CD", headers=auth_headers(manager))
    assert [v["id"] for v in found.json()["items"]] == [vehicle["id"]]

    by_name = await client.get("/api/v1/residents?q=dur", headers=auth_headers(manager))
    assert by_name.json()["total"] == 1
    by_plate = await client.get("/api/v1/residents?q=ab123", headers=auth_headers(manager))
    assert by_plate.json()["total"] == 1

    listed = await client.get(
        f"/api/v1/residents/{resident['id']}/vehicles", headers=auth_headers(manager)
    )
    assert [v["plate_norm"] for v in listed.json()] == ["AB123CD"]


async def test_plate_unique_per_tenant_only(
    client: AsyncClient, manager: User, site: Site, other_admin: User, other_site: Site
) -> None:
    resident = await _create_resident(client, manager, site)
    first = await client.post(
        "/api/v1/vehicles",
        json={"resident_id": resident["id"], "plate": "ZZ-001-ZZ"},
        headers=auth_headers(manager),
    )
    assert first.status_code == 201
    duplicate = await client.post(
        "/api/v1/vehicles",
        json={"resident_id": resident["id"], "plate": "zz 001 zz"},
        headers=auth_headers(manager),
    )
    assert duplicate.status_code == 409

    foreign_resident = await _create_resident(client, other_admin, other_site)
    same_plate_elsewhere = await client.post(
        "/api/v1/vehicles",
        json={"resident_id": foreign_resident["id"], "plate": "ZZ-001-ZZ"},
        headers=auth_headers(other_admin),
    )
    assert same_plate_elsewhere.status_code == 201


async def test_unknown_brand_and_implausible_plate_are_rejected(
    client: AsyncClient, manager: User, site: Site
) -> None:
    resident = await _create_resident(client, manager, site)
    bad_brand = await client.post(
        "/api/v1/vehicles",
        json={"resident_id": resident["id"], "plate": "AB-123-CD", "declared_brand": "zorglub"},
        headers=auth_headers(manager),
    )
    assert bad_brand.status_code == 400
    bad_plate = await client.post(
        "/api/v1/vehicles",
        json={"resident_id": resident["id"], "plate": "A1"},
        headers=auth_headers(manager),
    )
    assert bad_plate.status_code == 422


async def test_toggle_access_and_delete_cascade(
    client: AsyncClient, manager: User, site: Site
) -> None:
    resident = await _create_resident(client, manager, site)
    vehicle = (
        await client.post(
            "/api/v1/vehicles",
            json={"resident_id": resident["id"], "plate": "AB-123-CD"},
            headers=auth_headers(manager),
        )
    ).json()

    toggled = await client.post(
        f"/api/v1/vehicles/{vehicle['id']}/access",
        json={"enabled": False},
        headers=auth_headers(manager),
    )
    assert toggled.status_code == 200
    assert toggled.json()["access_enabled"] is False

    deleted = await client.delete(
        f"/api/v1/residents/{resident['id']}", headers=auth_headers(manager)
    )
    assert deleted.status_code == 204
    gone = await client.get(f"/api/v1/vehicles/{vehicle['id']}", headers=auth_headers(manager))
    assert gone.status_code == 404


async def test_scope_and_roles(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    agent: User,
    manager: User,
    site: Site,
    other_site: Site,
) -> None:
    hidden_site = await make_site(db_session, tenant, "Cache")
    visible = await make_resident(db_session, site, "Visible")
    hidden = await make_resident(db_session, hidden_site, "Cache")

    listed = await client.get("/api/v1/residents", headers=auth_headers(agent))
    ids = {r["id"] for r in listed.json()["items"]}
    assert str(visible.id) in ids
    assert str(hidden.id) not in ids

    forbidden_write = await client.post(
        "/api/v1/residents",
        json={"site_id": str(site.id), "last_name": "X", "first_name": "Y"},
        headers=auth_headers(agent),
    )
    assert forbidden_write.status_code == 403

    foreign = await client.post(
        "/api/v1/residents",
        json={"site_id": str(other_site.id), "last_name": "X", "first_name": "Y"},
        headers=auth_headers(manager),
    )
    assert foreign.status_code == 404
