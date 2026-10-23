"""Connexion, rafraîchissement, déconnexion, profil courant."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUserDep, SessionDep
from app.core.security import DUMMY_PASSWORD_HASH, verify_password
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.schemas.auth import LoginRequest, MeResponse, RefreshRequest, TokenPair
from app.schemas.tenant import TenantSummary
from app.services.auth import issue_tokens, revoke_refresh_token, rotate_refresh_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, session: SessionDep) -> TokenPair:
    user = await session.scalar(select(User).where(User.email == payload.email))
    # Vérification même si l'utilisateur est inconnu : temps de réponse constant.
    password_ok = verify_password(
        payload.password, user.password_hash if user else DUMMY_PASSWORD_HASH
    )
    if user is None or not password_ok or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiants invalides")
    user.last_login_at = datetime.now(UTC)
    tokens = await issue_tokens(session, user)
    await session.commit()
    return tokens


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, session: SessionDep) -> TokenPair:
    tokens = await rotate_refresh_token(session, payload.refresh_token)
    await session.commit()
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, session: SessionDep) -> None:
    await revoke_refresh_token(session, payload.refresh_token)
    await session.commit()


@router.get("/me", response_model=MeResponse)
async def me(current: CurrentUserDep, session: SessionDep) -> MeResponse:
    tenant = await session.get(Tenant, current.tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Locataire introuvable")
    return MeResponse(
        id=current.user.id,
        email=current.user.email,
        full_name=current.user.full_name,
        role=current.role,
        tenant=TenantSummary.model_validate(tenant),
        site_ids=[s.id for s in current.user.sites],
    )
