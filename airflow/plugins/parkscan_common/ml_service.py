"""Service d'inférence : rechargement à chaud des modèles après une promotion."""

from typing import Any

import requests

from parkscan_common import config


def reload_models() -> dict[str, Any]:
    response = requests.post(
        f"{config.ML_URL}/models/reload",
        headers={"X-Internal-Token": config.INTERNAL_TOKEN},
        timeout=max(config.HTTP_TIMEOUT, 180.0),
    )
    if response.status_code >= 400:
        raise RuntimeError(f"ml reload -> HTTP {response.status_code} : {response.text[:300]}")
    return response.json()
