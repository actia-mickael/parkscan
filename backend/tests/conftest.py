"""Isolation par transaction annulée à la fin de chaque test, client HTTP, et fabriques de données.

Une seule connexion par test, ouverte dans une transaction jamais validée. Les fixtures et chaque
requête HTTP travaillent dans des sessions distinctes sur cette connexion (chacune dans un point de
sauvegarde) : une annulation côté serveur, par exemple après un conflit 409, ne vide pas les objets
préparés par les fixtures.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

from app.core.config import get_settings
from app.core.plates import normalize_plate
from app.core.security import create_access_token, generate_api_key, hash_password
from app.db.models import ApiKey, Resident, Site, Tenant, User, UserRole, Vehicle
from app.db.session import get_session
from app.main import app

TEST_PASSWORD = "Secret-123"


def _session_on(conn: AsyncConnection) -> AsyncSession:
    return AsyncSession(bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint")


@pytest.fixture
async def db_conn() -> AsyncIterator[AsyncConnection]:
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as conn:
        transaction = await conn.begin()
        try:
            yield conn
        finally:
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
async def db_session(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = _session_on(db_conn)
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
async def client(db_conn: AsyncConnection) -> AsyncIterator[AsyncClient]:
    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with _session_on(db_conn) as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    try:
        async with (
            LifespanManager(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http,
        ):
            yield http
    finally:
        app.dependency_overrides.clear()


# --- Fabriques -----------------------------------------------------------------------------


async def make_tenant(session: AsyncSession, name: str = "Horizon Test") -> Tenant:
    tenant = Tenant(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)
    return tenant


async def make_site(session: AsyncSession, tenant: Tenant, name: str = "Site Test") -> Site:
    site = Site(tenant_id=tenant.id, name=name, slug=f"site-{uuid.uuid4().hex[:8]}")
    session.add(site)
    await session.commit()
    await session.refresh(site)
    return site


async def make_user(
    session: AsyncSession, tenant: Tenant, role: UserRole, sites: list[Site] | None = None
) -> User:
    user = User(
        tenant_id=tenant.id,
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.example",
        password_hash=hash_password(TEST_PASSWORD),
        full_name=f"Test {role.value}",
        role=role,
    )
    user.sites = list(sites or [])
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def make_api_key(session: AsyncSession, site: Site) -> tuple[ApiKey, str]:
    secret, prefix, digest = generate_api_key()
    api_key = ApiKey(
        tenant_id=site.tenant_id, site_id=site.id, name="test", key_prefix=prefix, key_hash=digest
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return api_key, secret


async def make_resident(
    session: AsyncSession, site: Site, last_name: str = "Test", first_name: str = "Resident"
) -> Resident:
    resident = Resident(
        tenant_id=site.tenant_id, site_id=site.id, last_name=last_name, first_name=first_name
    )
    session.add(resident)
    await session.commit()
    await session.refresh(resident)
    return resident


async def make_vehicle(
    session: AsyncSession, resident: Resident, plate: str, access_enabled: bool = True
) -> Vehicle:
    vehicle = Vehicle(
        tenant_id=resident.tenant_id,
        site_id=resident.site_id,
        resident_id=resident.id,
        plate_raw=plate,
        plate_norm=normalize_plate(plate),
        access_enabled=access_enabled,
    )
    session.add(vehicle)
    await session.commit()
    await session.refresh(vehicle)
    return vehicle


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def tenant(db_session: AsyncSession) -> Tenant:
    return await make_tenant(db_session)


@pytest.fixture
async def other_tenant(db_session: AsyncSession) -> Tenant:
    return await make_tenant(db_session, "Autre Operateur")


@pytest.fixture
async def site(db_session: AsyncSession, tenant: Tenant) -> Site:
    return await make_site(db_session, tenant)


@pytest.fixture
async def other_site(db_session: AsyncSession, other_tenant: Tenant) -> Site:
    return await make_site(db_session, other_tenant, "Site Etranger")


@pytest.fixture
async def admin(db_session: AsyncSession, tenant: Tenant) -> User:
    return await make_user(db_session, tenant, UserRole.operator_admin)


@pytest.fixture
async def manager(db_session: AsyncSession, tenant: Tenant, site: Site) -> User:
    return await make_user(db_session, tenant, UserRole.site_manager, [site])


@pytest.fixture
async def agent(db_session: AsyncSession, tenant: Tenant, site: Site) -> User:
    return await make_user(db_session, tenant, UserRole.agent, [site])


@pytest.fixture
async def other_admin(db_session: AsyncSession, other_tenant: Tenant) -> User:
    return await make_user(db_session, other_tenant, UserRole.operator_admin)
