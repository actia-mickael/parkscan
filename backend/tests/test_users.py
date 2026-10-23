from httpx import AsyncClient

from app.db.models import Site, User
from tests.conftest import TEST_PASSWORD, auth_headers


async def test_admin_creates_user_with_sites_and_new_user_can_login(
    client: AsyncClient, admin: User, site: Site, other_site: Site
) -> None:
    created = await client.post(
        "/api/v1/users",
        json={
            "email": "Nouveau@Test.example",
            "password": TEST_PASSWORD,
            "role": "agent",
            "site_ids": [str(site.id)],
        },
        headers=auth_headers(admin),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["email"] == "nouveau@test.example"
    assert body["site_ids"] == [str(site.id)]

    login = await client.post(
        "/api/v1/auth/login", json={"email": "nouveau@test.example", "password": TEST_PASSWORD}
    )
    assert login.status_code == 200

    duplicate = await client.post(
        "/api/v1/users",
        json={"email": "nouveau@test.example", "password": TEST_PASSWORD, "role": "agent"},
        headers=auth_headers(admin),
    )
    assert duplicate.status_code == 409

    foreign_site = await client.post(
        "/api/v1/users",
        json={
            "email": "autre@test.example",
            "password": TEST_PASSWORD,
            "role": "agent",
            "site_ids": [str(other_site.id)],
        },
        headers=auth_headers(admin),
    )
    assert foreign_site.status_code == 404


async def test_admin_updates_sites_and_cannot_delete_self(
    client: AsyncClient, admin: User, agent: User, site: Site
) -> None:
    cleared = await client.put(
        f"/api/v1/users/{agent.id}/sites", json={"site_ids": []}, headers=auth_headers(admin)
    )
    assert cleared.status_code == 200
    assert cleared.json()["site_ids"] == []

    restored = await client.put(
        f"/api/v1/users/{agent.id}/sites",
        json={"site_ids": [str(site.id)]},
        headers=auth_headers(admin),
    )
    assert restored.json()["site_ids"] == [str(site.id)]

    self_delete = await client.delete(f"/api/v1/users/{admin.id}", headers=auth_headers(admin))
    assert self_delete.status_code == 400

    deleted = await client.delete(f"/api/v1/users/{agent.id}", headers=auth_headers(admin))
    assert deleted.status_code == 204
    gone = await client.get(f"/api/v1/users/{agent.id}", headers=auth_headers(admin))
    assert gone.status_code == 404


async def test_users_are_isolated_per_tenant(
    client: AsyncClient, admin: User, other_admin: User
) -> None:
    listed = await client.get("/api/v1/users", headers=auth_headers(other_admin))
    assert listed.status_code == 200
    assert str(admin.id) not in {u["id"] for u in listed.json()}

    direct = await client.get(f"/api/v1/users/{admin.id}", headers=auth_headers(other_admin))
    assert direct.status_code == 404
