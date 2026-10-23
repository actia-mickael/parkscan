"""Appels au backend ParkScan avec le jeton interne (routes /training et /models)."""

from typing import Any

import requests

from parkscan_common import config


def _headers() -> dict[str, str]:
    return {"X-Internal-Token": config.INTERNAL_TOKEN}


def get(path: str, **params: Any) -> Any:
    response = requests.get(
        f"{config.BACKEND_URL}{path}",
        headers=_headers(),
        params=params,
        timeout=config.HTTP_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def post(path: str, body: dict[str, Any] | None = None) -> Any:
    response = requests.post(
        f"{config.BACKEND_URL}{path}",
        headers=_headers(),
        json=body or {},
        timeout=config.HTTP_TIMEOUT,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"backend {path} -> HTTP {response.status_code} : {response.text[:300]}")
    return response.json()
