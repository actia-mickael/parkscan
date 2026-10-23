"""Réentraînement : état de préparation, échantillons étiquetés, construction d'une version du jeu."""

from uuid import UUID

from pydantic import BaseModel, Field


class TrainingReadiness(BaseModel):
    new_validated: int  # écarts validés pas encore inclus dans une version du jeu
    total_labeled: int  # jeu cumulé (validés + déjà exportés) disposant d'une image
    min_dataset_size: int
    ready: bool
    by_brand: dict[str, int]  # jeu cumulé par marque


class TrainingSample(BaseModel):
    id: UUID
    tenant_id: UUID
    brand: str
    key: str
    exported: bool
    dataset_version: str | None


class DatasetBuildRequest(BaseModel):
    val_ratio: float = Field(default=0.2, gt=0, lt=0.5)
    seed: int = 42
    min_per_class: int = Field(default=2, ge=1)  # en dessous, la marque est écartée du jeu


class DatasetBuildResult(BaseModel):
    dataset_version: str
    bucket: str
    manifest_key: str
    summary_key: str
    samples: int
    new_samples: int
    train: int
    val: int
    classes: dict[str, int]
    dropped: dict[str, int]
