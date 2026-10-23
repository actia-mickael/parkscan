"""Émission, rotation et révocation des jetons."""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import TokenError, create_access_token, create_refresh_token, decode_token
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User
from app.schemas.auth import TokenPair


def _invalid() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton de rafraîchissement invalide")


async def issue_tokens(session: AsyncSession, user: User) -> TokenPair:
    settings = get_settings()
    jti = uuid.uuid4()
    refresh, expires_at = create_refresh_token(user_id=user.id, jti=jti)
    session.add(RefreshToken(jti=jti, user_id=user.id, expires_at=expires_at))
    access = create_access_token(user_id=user.id, tenant_id=user.tenant_id, role=user.role.value)
    return TokenPair(
        access_token=access, refresh_token=refresh, expires_in=settings.jwt_access_minutes * 60
    )


async def rotate_refresh_token(session: AsyncSession, token: str) -> TokenPair:
    """Un jeton de rafraîchissement ne sert qu'une fois : il est révoqué et remplacé."""
    try:
        payload = decode_token(token, expected_type="refresh")
    except TokenError as exc:
        raise _invalid() from exc
    now = datetime.now(UTC)
    row = await session.get(RefreshToken, uuid.UUID(payload["jti"]))
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        raise _invalid()
    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise _invalid()
    row.revoked_at = now
    return await issue_tokens(session, user)


async def revoke_refresh_token(session: AsyncSession, token: str) -> None:
    try:
        payload = decode_token(token, expected_type="refresh")
    except TokenError:
        return
    row = await session.get(RefreshToken, uuid.UUID(payload["jti"]))
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
