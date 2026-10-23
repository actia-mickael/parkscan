from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.mismatch_review import ReviewOutcome, ReviewStatus


class MismatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    site_id: UUID
    passage_id: UUID
    vehicle_id: UUID | None
    predicted_brand: str
    predicted_conf: float
    declared_brand: str | None
    status: ReviewStatus
    outcome: ReviewOutcome | None
    final_brand: str | None
    reviewer_id: UUID | None
    reviewed_at: datetime | None
    comment: str | None
    source_crop_key: str | None
    dataset_key: str | None
    created_at: datetime
    # Contexte du passage, pour la file de validation
    plate_norm: str | None = None
    received_at: datetime | None = None


class ValidateRequest(BaseModel):
    outcome: Literal["predicted_correct", "declared_correct", "custom"]
    final_brand: str | None = Field(default=None, max_length=40)
    update_vehicle: bool = True
    comment: str | None = None


class RejectRequest(BaseModel):
    comment: str | None = None


class MismatchStats(BaseModel):
    pending: int
    validated: int
    rejected: int
    exported: int
    validated_by_brand: dict[str, int]
    min_dataset_size: int
    ready_for_retraining: bool
