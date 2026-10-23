"""Gestion des utilisateurs du locataire (administrateur uniquement)."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import AdminDep, SessionDep
from app.core.security import hash_password
from app.db.models.user import User
from app.schemas.user import UserCreate, UserRead, UserSitesUpdate, UserUpdate
from app.services.db import save
from app.services.sites import load_tenant_sites

router = APIRouter(prefix="/users", tags=["users"])
EMAIL_CONFLICT = "Adresse e-mail déjà utilisée"


async def _get_user(session: SessionDep, current: AdminDep, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None or user.tenant_id != current.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable")
    return user


@router.get("", response_model=list[UserRead])
async def list_users(current: AdminDep, session: SessionDep) -> list[UserRead]:
    result = await session.scalars(
        select(User).where(User.tenant_id == current.tenant_id).order_by(User.created_at)
    )
    return [UserRead.from_model(u) for u in result]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, current: AdminDep, session: SessionDep) -> UserRead:
    user = User(
        tenant_id=current.tenant_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    user.sites = await load_tenant_sites(session, current.tenant_id, payload.site_ids)
    session.add(user)
    await save(session, user, conflict=EMAIL_CONFLICT)
    return UserRead.from_model(user)


@router.get("/{user_id}", response_model=UserRead)
async def read_user(user_id: uuid.UUID, current: AdminDep, session: SessionDep) -> UserRead:
    return UserRead.from_model(await _get_user(session, current, user_id))


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID, payload: UserUpdate, current: AdminDep, session: SessionDep
) -> UserRead:
    user = await _get_user(session, current, user_id)
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        if user.id == current.user.id and not payload.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Impossible de se désactiver soi-même")
        user.is_active = payload.is_active
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    await save(session, user, conflict=EMAIL_CONFLICT)
    return UserRead.from_model(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, current: AdminDep, session: SessionDep) -> None:
    user = await _get_user(session, current, user_id)
    if user.id == current.user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Impossible de se supprimer soi-même")
    await session.delete(user)
    await session.commit()


@router.put("/{user_id}/sites", response_model=UserRead)
async def set_user_sites(
    user_id: uuid.UUID, payload: UserSitesUpdate, current: AdminDep, session: SessionDep
) -> UserRead:
    user = await _get_user(session, current, user_id)
    user.sites = await load_tenant_sites(session, current.tenant_id, payload.site_ids)
    await save(session, user)
    return UserRead.from_model(user)
