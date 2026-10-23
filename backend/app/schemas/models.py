"""Modèles servis par le service ML (miroir de ml/parkscan_ml/schemas.py : ModelsResponse)."""

from pydantic import BaseModel, Field


class ServedModel(BaseModel):
    source: str  # "local", "mlflow"…
    version: str
    details: dict[str, str | int | float | None] = Field(default_factory=dict)


class ServedModels(BaseModel):
    device: str
    models: dict[str, ServedModel]
    labels: list[str]


# --- Versions et promotions (registre vu du backend) ------------------------------------------

from datetime import datetime  # noqa: E402
from typing import Any  # noqa: E402
from uuid import UUID  # noqa: E402

from pydantic import ConfigDict  # noqa: E402

from app.db.models.model_version import ModelVersionStatus, PromotionDecision  # noqa: E402


class ModelVersionCreate(BaseModel):
    name: str = Field(max_length=60)
    version: int = Field(ge=1)
    run_id: str | None = Field(default=None, max_length=64)
    source: str | None = Field(default=None, max_length=255)
    dataset_version: str | None = Field(default=None, max_length=40)
    metrics: dict[str, float] | None = None
    baseline_metrics: dict[str, float] | None = None
    labels_count: int | None = None


class ModelVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    version: int
    run_id: str | None
    source: str | None
    status: ModelVersionStatus
    dataset_version: str | None
    metrics: dict[str, Any] | None
    baseline_metrics: dict[str, Any] | None
    labels_count: int | None
    promoted_at: datetime | None
    created_at: datetime


class PromotionCreate(BaseModel):
    name: str = Field(max_length=60)
    version: int = Field(ge=1)
    decision: PromotionDecision
    reason: str | None = None
    candidate_metrics: dict[str, float] | None = None
    baseline_metrics: dict[str, float] | None = None
    decided_by: str = Field(default="airflow", max_length=60)


class PromotionRead(BaseModel):
    id: UUID
    model_version_id: UUID
    name: str
    version: int
    decision: PromotionDecision
    reason: str | None
    candidate_metrics: dict[str, Any] | None
    baseline_metrics: dict[str, Any] | None
    previous_version: int | None
    decided_by: str
    created_at: datetime
