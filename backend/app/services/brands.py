"""Accès au référentiel de marques (alias) pour la règle d'écart."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.brands import build_alias_map
from app.db.models.brand import Brand


async def load_alias_map(session: AsyncSession) -> dict[str, str]:
    rows = (await session.execute(select(Brand.slug, Brand.aliases))).all()
    return build_alias_map([(slug, list(aliases or [])) for slug, aliases in rows])


async def ensure_brand(session: AsyncSession, slug: str, display_name: str | None = None) -> Brand:
    """Retourne la marque, en la créant si elle est inconnue (marque saisie à la validation)."""
    brand = await session.get(Brand, slug)
    if brand is None:
        brand = Brand(slug=slug, display_name=display_name or slug.capitalize(), aliases=[])
        session.add(brand)
        await session.flush()
    return brand
