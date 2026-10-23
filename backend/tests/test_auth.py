from httpx import AsyncClient

from app.db.models import User
from tests.conftest import TEST_PASSWORD, auth_headers


async def test_login_returns_tokens_and_me(client: AsyncClient, admin: User) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": admin.email.upper(), "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    tokens = response.json()
    assert tokens["token_type"] == "bearer"

    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == admin.email
    assert me.json()["role"] == "operator_admin"
    assert me.json()["tenant"]["id"] == str(admin.tenant_id)


async def test_login_rejects_bad_password_and_unknown_email(
    client: AsyncClient, admin: User
) -> None:
    bad = await client.post(
        "/api/v1/auth/login", json={"email": admin.email, "password": "mauvais-mot-de-passe"}
    )
    assert bad.status_code == 401
    unknown = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@test.example", "password": TEST_PASSWORD}
    )
    assert unknown.status_code == 401


async def test_me_requires_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    forged = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer abc.def.ghi"})
    assert forged.status_code == 401


async def test_refresh_rotates_and_logout_revokes(client: AsyncClient, admin: User) -> None:
    login = await client.post(
        "/api/v1/auth/login", json={"email": admin.email, "password": TEST_PASSWORD}
    )
    first_refresh = login.json()["refresh_token"]

    rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert rotated.status_code == 200
    second_refresh = rotated.json()["refresh_token"]
    assert second_refresh != first_refresh

    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert reused.status_code == 401

    logout = await client.post("/api/v1/auth/logout", json={"refresh_token": second_refresh})
    assert logout.status_code == 204
    after_logout = await client.post("/api/v1/auth/refresh", json={"refresh_token": second_refresh})
    assert after_logout.status_code == 401


async def test_inactive_user_is_rejected(client: AsyncClient, admin: User, db_session) -> None:
    admin.is_active = False
    await db_session.commit()
    response = await client.get("/api/v1/auth/me", headers=auth_headers(admin))
    assert response.status_code == 401
