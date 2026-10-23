"""Client de l'API d'ingestion : envoi d'une capture avec identifiant de requête rejouable."""

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from parkscan_edge.config import EdgeSettings


class ApiUnreachableError(Exception):
    """L'API n'a pas répondu après les tentatives prévues."""


@dataclass(slots=True)
class CaptureResult:
    decision: str
    reason: str
    plate_norm: str | None
    brand: str | None
    is_mismatch: bool
    latency_ms: int | None
    duplicate: bool
    round_trip_ms: int


class CaptureClient:
    def __init__(self, settings: EdgeSettings) -> None:
        self._settings = settings
        self._http = httpx.Client(
            base_url=settings.api_url,
            headers={"X-Api-Key": settings.api_key},
            timeout=httpx.Timeout(settings.timeout_s, connect=1.0),
        )

    def send(
        self, image: bytes, request_id: str | None = None, captured_at: datetime | None = None
    ) -> CaptureResult:
        # L'identifiant est fixé AVANT le premier envoi : un rejeu ne crée jamais un second passage.
        request_id = request_id or uuid.uuid4().hex
        payload = {
            "client_request_id": request_id,
            "captured_at": (captured_at or datetime.now(UTC)).isoformat(),
            "run_brand": "true" if self._settings.run_brand else "false",
        }
        last_error: Exception | None = None
        for _ in range(self._settings.retries + 1):
            started = time.perf_counter()
            try:
                response = self._http.post(
                    "/api/v1/ingest/capture",
                    files={"image": ("capture.jpg", image, "image/jpeg")},
                    data=payload,
                )
                response.raise_for_status()
                body = response.json()
                return CaptureResult(
                    decision=body["decision"],
                    reason=body["reason"],
                    plate_norm=body.get("plate_norm"),
                    brand=body.get("brand"),
                    is_mismatch=body.get("is_mismatch", False),
                    latency_ms=body.get("latency_ms"),
                    duplicate=body.get("duplicate", False),
                    round_trip_ms=int((time.perf_counter() - started) * 1000),
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (401, 403, 413, 422, 429):
                    raise  # inutile de réessayer : clé, taille ou quota en cause
                last_error = exc
            except httpx.HTTPError as exc:
                last_error = exc
        raise ApiUnreachableError(str(last_error))

    def close(self) -> None:
        self._http.close()
