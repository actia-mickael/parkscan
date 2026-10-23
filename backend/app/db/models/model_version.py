"""Versions du classifieur de marques connues du backend et décisions de promotion (modèle global)."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ModelVersionStatus(enum.StrEnum):
    candidate = "candidate"
    production = "production"
    previous = "previous"
    rejected = "rejected"
    archived = "archived"


class PromotionDecision(enum.StrEnum):
    promoted = "promoted"
    rejected = "rejected"


def _enum(cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class ModelVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Une version d'un modèle enregistré dans MLflow (nom + numéro), avec ses métriques."""

    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_model_versions_name_version"),)

    name: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[ModelVersionStatus] = mapped_column(
        _enum(ModelVersionStatus, "model_version_status"),
        nullable=False,
        default=ModelVersionStatus.candidate,
    )
    dataset_version: Mapped[str | None] = mapped_column(String(40))
    # Métriques du candidat et du modèle de production évalué sur le même jeu de validation
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    baseline_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    labels_count: Mapped[int | None] = mapped_column(Integer)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModelPromotion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Décision prise sur une version candidate : promue en production ou rejetée, et pourquoi."""

    __tablename__ = "model_promotions"

    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_versions.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[PromotionDecision] = mapped_column(
        _enum(PromotionDecision, "promotion_decision"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text)
    candidate_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    baseline_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    previous_version: Mapped[int | None] = mapped_column(Integer)
    decided_by: Mapped[str] = mapped_column(String(60), nullable=False, default="airflow")
