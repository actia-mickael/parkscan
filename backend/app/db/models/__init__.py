"""Importe tous les modèles pour qu'Alembic et SQLAlchemy les connaissent."""

from app.db.models.api_key import ApiKey
from app.db.models.brand import Brand
from app.db.models.mismatch_review import MismatchReview, ReviewOutcome, ReviewStatus
from app.db.models.model_version import (
    ModelPromotion,
    ModelVersion,
    ModelVersionStatus,
    PromotionDecision,
)
from app.db.models.passage import Decision, Passage, PassageStatus
from app.db.models.refresh_token import RefreshToken
from app.db.models.resident import Resident
from app.db.models.site import Site
from app.db.models.tenant import Tenant
from app.db.models.user import User, UserRole, user_sites
from app.db.models.vehicle import Vehicle

__all__ = [
    "ApiKey",
    "Brand",
    "Decision",
    "MismatchReview",
    "ModelPromotion",
    "ModelVersion",
    "ModelVersionStatus",
    "Passage",
    "PassageStatus",
    "PromotionDecision",
    "RefreshToken",
    "Resident",
    "ReviewOutcome",
    "ReviewStatus",
    "Site",
    "Tenant",
    "User",
    "UserRole",
    "Vehicle",
    "user_sites",
]
