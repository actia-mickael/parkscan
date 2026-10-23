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
