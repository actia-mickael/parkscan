"""Aides de persistance communes aux routeurs."""

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def commit_or_conflict(session: AsyncSession, detail: str) -> None:
    """Valide la transaction ; une violation de contrainte devient une réponse 409."""
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail) from exc


async def save(session: AsyncSession, obj: object, *, conflict: str = "Conflit de données") -> None:
    """Valide puis recharge l'objet : les valeurs calculées en base (id, horodatages) sont à jour."""
    await commit_or_conflict(session, conflict)
    await session.refresh(obj)
