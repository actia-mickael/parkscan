"""Jeu de démonstration fictif : référentiel de marques, un locataire, deux sites, trois utilisateurs,
une clé API par site. Idempotent : relançable sans doublon. Usage : python -m app.seed.seed_demo"""

import asyncio
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import generate_api_key, hash_password
from app.db.models import ApiKey, Brand, Site, Tenant, User, UserRole
from app.db.session import SessionLocal

HERE = Path(__file__).parent


async def seed_brands(session: AsyncSession) -> int:
    entries = json.loads((HERE / "brands.json").read_text(encoding="utf-8"))
    existing = {b.slug: b for b in await session.scalars(select(Brand))}
    for entry in entries:
        brand = existing.get(entry["slug"])
        if brand is None:
            session.add(
                Brand(
                    slug=entry["slug"],
                    display_name=entry["display_name"],
                    aliases=entry.get("aliases", []),
                    in_model=entry.get("in_model", False),
                )
            )
        else:
            brand.display_name = entry["display_name"]
            brand.aliases = entry.get("aliases", [])
    return len(entries)


async def seed_tenant(session: AsyncSession, data: dict) -> Tenant:
    tenant = await session.scalar(select(Tenant).where(Tenant.slug == data["slug"]))
    if tenant is None:
        tenant = Tenant(name=data["name"], slug=data["slug"], settings=data["settings"])
        session.add(tenant)
        await session.flush()
    return tenant


async def seed_sites(session: AsyncSession, tenant: Tenant, entries: list[dict]) -> dict[str, Site]:
    sites: dict[str, Site] = {}
    for entry in entries:
        site = await session.scalar(
            select(Site).where(Site.tenant_id == tenant.id, Site.slug == entry["slug"])
        )
        if site is None:
            site = Site(tenant_id=tenant.id, **entry)
            session.add(site)
            await session.flush()
        sites[site.slug] = site
    return sites


async def seed_users(
    session: AsyncSession, tenant: Tenant, sites: dict[str, Site], entries: list[dict]
) -> None:
    settings = get_settings()
    for entry in entries:
        user = await session.scalar(select(User).where(User.email == entry["email"]))
        if user is None:
            user = User(
                tenant_id=tenant.id,
                email=entry["email"],
                full_name=entry["full_name"],
                role=UserRole(entry["role"]),
                password_hash=hash_password(getattr(settings, entry["password_setting"])),
            )
            session.add(user)
        user.sites = [sites[slug] for slug in entry["sites"]]


async def seed_api_keys(session: AsyncSession, sites: dict[str, Site]) -> list[tuple[str, str]]:
    created: list[tuple[str, str]] = []
    for slug, site in sites.items():
        active = await session.scalar(
            select(ApiKey).where(ApiKey.site_id == site.id, ApiKey.revoked_at.is_(None))
        )
        if active is not None:
            continue
        secret, prefix, digest = generate_api_key()
        session.add(
            ApiKey(
                tenant_id=site.tenant_id,
                site_id=site.id,
                name="Agent de bord (démo)",
                key_prefix=prefix,
                key_hash=digest,
            )
        )
        created.append((slug, secret))
    return created


async def main() -> None:
    data = json.loads((HERE / "demo_data.json").read_text(encoding="utf-8"))
    async with SessionLocal() as session:
        n_brands = await seed_brands(session)
        tenant = await seed_tenant(session, data["tenant"])
        sites = await seed_sites(session, tenant, data["sites"])
        await seed_users(session, tenant, sites, data["users"])
        keys = await seed_api_keys(session, sites)
        await session.commit()

    print(f"[seed] marques : {n_brands} | locataire : {tenant.name} | sites : {', '.join(sites)}")
    print("[seed] utilisateurs : " + ", ".join(u["email"] for u in data["users"]))
    if keys:
        print("[seed] clés API créées (secret affiché une seule fois) :")
        for slug, secret in keys:
            print(f"  {slug}: {secret}")
    else:
        print("[seed] clés API : déjà présentes, aucune créée")


if __name__ == "__main__":
    asyncio.run(main())
