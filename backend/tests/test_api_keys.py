from httpx import AsyncClient

from app.db.models import Site, User
from tests.conftest import auth_headers


async def test_manager_creates_lists_and_revokes_key(
    client: AsyncClient, manager: User, site: Site
) -> None:
    created = await client.post(
        f"/api/v1/sites/{site.id}/api-keys",
        json={"name": "Barrière entrée"},
        headers=auth_headers(manager),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["secret"].startswith("psk_")
    assert body["key_prefix"] == body["secret"][:12]

    listed = await client.get(f"/api/v1/sites/{site.id}/api-keys", headers=auth_headers(manager))
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert "secret" not in listed.json()[0]
    assert listed.json()[0]["revoked_at"] is None

    revoked = await client.delete(f"/api/v1/api-keys/{body['id']}", headers=auth_headers(manager))
    assert revoked.status_code == 204
    listed_after = await client.get(
        f"/api/v1/sites/{site.id}/api-keys", headers=auth_headers(manager)
    )
    assert listed_after.json()[0]["revoked_at"] is not None


async def test_agent_cannot_manage_keys_and_scope_is_enforced(
    client: AsyncClient, agent: User, manager: User, site: Site, other_site: Site
) -> None:
    forbidden = await client.post(
        f"/api/v1/sites/{site.id}/api-keys", json={"name": "x"}, headers=auth_headers(agent)
    )
    assert forbidden.status_code == 403

    foreign = await client.post(
        f"/api/v1/sites/{other_site.id}/api-keys",
        json={"name": "x"},
        headers=auth_headers(manager),
    )
    assert foreign.status_code == 404
