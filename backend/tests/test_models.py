"""Modèles servis : lecture pour tout utilisateur, rechargement réservé à l'administrateur."""

from httpx import AsyncClient

from app.db.models import User
from tests.conftest import auth_headers
from tests.fakes import FakeMlClient


async def test_models_visible_to_any_user(client: AsyncClient, agent: User) -> None:
    response = await client.get("/api/v1/models", headers=auth_headers(agent))
    assert response.status_code == 200
    body = response.json()
    assert body["models"]["brand_classifier"]["source"] == "fake"
    assert "renault" in body["labels"]


async def test_models_require_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/models")).status_code == 401


async def test_models_unavailable_returns_503(
    client: AsyncClient, agent: User, fake_ml: FakeMlClient
) -> None:
    fake_ml.unavailable = True
    response = await client.get("/api/v1/models", headers=auth_headers(agent))
    assert response.status_code == 503


async def test_reload_requires_admin(
    client: AsyncClient, manager: User, admin: User, fake_ml: FakeMlClient
) -> None:
    denied = await client.post("/api/v1/models/reload", headers=auth_headers(manager))
    assert denied.status_code == 403
    assert fake_ml.reloads == 0

    ok = await client.post("/api/v1/models/reload", headers=auth_headers(admin))
    assert ok.status_code == 200
    assert fake_ml.reloads == 1
    assert ok.json()["models"]["brand_classifier"]["version"] == "fake"
