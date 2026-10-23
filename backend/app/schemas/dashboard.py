from datetime import datetime

from pydantic import BaseModel


class BrandCount(BaseModel):
    brand: str
    count: int


class HourlyPoint(BaseModel):
    hour: datetime
    allowed: int
    denied: int


class DashboardSummary(BaseModel):
    period_hours: int
    passages: int
    allowed: int
    denied: int
    mismatches: int
    failed: int  # statut différent de ok (pas de plaque, lecture faible, ML indisponible)
    pending_reviews: int
    latency_avg_ms: float | None
    latency_p95_ms: float | None
    top_brands: list[BrandCount]
    hourly: list[HourlyPoint]
