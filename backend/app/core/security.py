"""Hachage des mots de passe (argon2), jetons JWT (accès et rafraîchissement), clés API."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher()
TokenType = Literal["access", "refresh"]
API_KEY_PREFIX = "psk_"


class TokenError(Exception):
    """Jeton absent, invalide, expiré ou du mauvais type."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# Haché une fois au chargement : sert à égaliser le temps de réponse quand l'e-mail est inconnu.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


def _now() -> datetime:
    return datetime.now(UTC)


def create_access_token(*, user_id: uuid.UUID, tenant_id: uuid.UUID, role: str) -> str:
    settings = get_settings()
    now = _now()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(*, user_id: uuid.UUID, jti: uuid.UUID) -> tuple[str, datetime]:
    settings = get_settings()
    now = _now()
    expires_at = now + timedelta(days=settings.jwt_refresh_days)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "jti": str(jti),
        "type": "refresh",
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm), expires_at


def decode_token(token: str, *, expected_type: TokenType) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if payload.get("type") != expected_type or "sub" not in payload:
        raise TokenError("type de jeton inattendu")
    return payload


def generate_api_key() -> tuple[str, str, str]:
    """Retourne (secret complet, préfixe affichable, empreinte sha256). Le secret n'est jamais stocké."""
    secret = API_KEY_PREFIX + secrets.token_urlsafe(32)
    return secret, secret[: len(API_KEY_PREFIX) + 8], hash_api_key(secret)


def hash_api_key(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()
