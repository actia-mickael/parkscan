"""Isolation entre locataires et restriction par site selon le rôle."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Site, Tenant, User
from tests.conftest import auth_headers, make_site


async def test_admin_sees_only_own_tenant_sites(
    client: AsyncClient, admin: User, site: Site, other_site: Site
) -> None:
    response = await client.get("/api/v1/sites", headers=auth_headers(admin))
    assert response.status_code == 200
    ids = {s["id"] for s in response.json()}
    assert str(site.id) in ids
    assert str(other_site.id) not in ids

    foreign = await client.get(f"/api/v1/sites/{other_site.id}", headers=auth_headers(admin))
    assert foreign.status_code == 404


async def test_agent_sees_only_allowed_sites(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, agent: User, site: Site
) -> None:
    hidden = await make_site(db_session, tenant, "Site non autorise")
    response = await client.get("/api/v1/sites", headers=auth_headers(agent))
    ids = {s["id"] for s in response.json()}
    assert ids == {str(site.id)}

    forbidden = await client.get(f"/api/v1/sites/{hidden.id}", headers=auth_headers(agent))
    assert forbidden.status_code == 404


async def test_agent_cannot_write(client: AsyncClient, agent: User) -> None:
    create = await client.post("/api/v1/sites", json={"name": "X"}, headers=auth_headers(agent))
    assert create.status_code == 403
    users = await client.get("/api/v1/users", headers=auth_headers(agent))
    assert users.status_code == 403


async def test_admin_creates_site_with_generated_slug_and_rejects_duplicate(
    client: AsyncClient, admin: User
) -> None:
    created = await client.post(
        "/api/v1/sites", json={"name": "Parking Côté Mer"}, headers=auth_headers(admin)
    )
    assert created.status_code == 201
    assert created.json()["slug"] == "parking-cote-mer"
    assert created.json()["tenant_id"] == str(admin.tenant_id)

    duplicate = await client.post(
        "/api/v1/sites",
        json={"name": "Autre nom", "slug": "parking-cote-mer"},
        headers=auth_headers(admin),
    )
    assert duplicate.status_code == 409


async def test_other_tenant_admin_cannot_update_site(
    client: AsyncClient, other_admin: User, site: Site
) -> None:
    response = await client.patch(
        f"/api/v1/sites/{site.id}", json={"name": "Pirate"}, headers=auth_headers(other_admin)
    )
    assert response.status_code == 404
