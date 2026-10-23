"""Client HTTP du service ML. Toute défaillance (délai, connexion, 5xx) devient MlUnavailableError."""

import httpx

from app.core.config import Settings
from app.schemas.ml import MlInferResult


class MlUnavailableError(Exception):
    """Le service ML n'a pas répondu correctement dans le délai imparti."""


class MlRejectedError(Exception):
    """Le service ML a refusé la requête (image illisible, paramètres invalides)."""


class MlClient:
    def __init__(self, settings: Settings) -> None:
        self._http = httpx.AsyncClient(
            base_url=settings.ml_url,
            timeout=httpx.Timeout(settings.ml_timeout_ms / 1000, connect=2.0),
        )
        self._internal_token = settings.internal_token

    async def infer(
        self,
        image: bytes,
        *,
        det_threshold: float,
        vehicle_threshold: float,
        run_branch2: bool,
    ) -> MlInferResult:
        try:
            response = await self._http.post(
                "/infer",
                files={"image": ("capture.jpg", image, "image/jpeg")},
                data={
                    "det_threshold": str(det_threshold),
                    "vehicle_threshold": str(vehicle_threshold),
                    "run_branch2": "true" if run_branch2 else "false",
                },
            )
        except httpx.HTTPError as exc:
            # Un délai dépassé (ReadTimeout) n'a pas de message : on journalise au moins le type.
            raise MlUnavailableError(str(exc) or type(exc).__name__) from exc
        if response.status_code >= 500:
            raise MlUnavailableError(f"HTTP {response.status_code}")
        if response.status_code >= 400:
            raise MlRejectedError(response.text[:200])
        return MlInferResult.model_validate(response.json())

    async def health(self) -> bool:
        try:
            response = await self._http.get("/health")
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    async def models(self) -> dict:
        try:
            response = await self._http.get("/models", timeout=10)
        except httpx.HTTPError as exc:
            raise MlUnavailableError(str(exc) or type(exc).__name__) from exc
        if response.status_code >= 500:
            raise MlUnavailableError(f"HTTP {response.status_code}")
        response.raise_for_status()
        return response.json()

    async def reload(self) -> dict:
        response = await self._http.post(
            "/models/reload", headers={"X-Internal-Token": self._internal_token}, timeout=120
        )
        response.raise_for_status()
        return response.json()

    async def aclose(self) -> None:
        await self._http.aclose()
