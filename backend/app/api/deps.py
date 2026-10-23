"""Dépendances FastAPI partagées : session, utilisateur courant, rôles, jeton interne."""

import secrets
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import TokenError, decode_token
from app.db.models.user import User, UserRole
from app.db.session import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class CurrentUser:
    user: User
    # None : accès à tous les sites du locataire (administrateur). Sinon, sites explicitement autorisés.
    allowed_site_ids: set[uuid.UUID] | None

    @property
    def tenant_id(self) -> uuid.UUID:
        return self.user.tenant_id

    @property
    def role(self) -> UserRole:
        return self.user.role

    def can_access_site(self, site_id: uuid.UUID) -> bool:
        return self.allowed_site_ids is None or site_id in self.allowed_site_ids


def _unauthorized(detail: str = "Authentification requise") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: SessionDep,
) -> CurrentUser:
    if credentials is None:
        raise _unauthorized()
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except TokenError as exc:
        raise _unauthorized("Jeton invalide ou expiré") from exc
    user = await session.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise _unauthorized("Compte inconnu ou désactivé")
    allowed = None if user.role == UserRole.operator_admin else {s.id for s in user.sites}
    return CurrentUser(user=user, allowed_site_ids=allowed)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[..., Awaitable[CurrentUser]]:
    async def _check(current: CurrentUserDep) -> CurrentUser:
        if current.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Rôle insuffisant pour cette action")
        return current

    return _check


AdminDep = Annotated[CurrentUser, Depends(require_roles(UserRole.operator_admin))]
ManagerDep = Annotated[
    CurrentUser, Depends(require_roles(UserRole.operator_admin, UserRole.site_manager))
]


async def require_internal_token(
    x_internal_token: Annotated[str | None, Header()] = None,
) -> None:
    expected = get_settings().internal_token
    if x_internal_token is None or not secrets.compare_digest(x_internal_token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton interne invalide")


InternalDep = Annotated[None, Depends(require_internal_token)]
