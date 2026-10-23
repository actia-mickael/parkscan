"""Registre MLflow par son API REST (pas de client Python : l'image Airflow reste légère)."""

from typing import Any

import requests

from parkscan_common import config

API = "/api/2.0/mlflow"


def _call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    response = requests.request(
        method, f"{config.MLFLOW_URL}{API}{path}", timeout=config.HTTP_TIMEOUT, **kwargs
    )
    if response.status_code >= 400:
        raise RuntimeError(f"mlflow {path} -> HTTP {response.status_code} : {response.text[:300]}")
    return response.json() if response.content else {}


def _tags(entity: dict[str, Any]) -> dict[str, str]:
    return {t["key"]: t["value"] for t in entity.get("tags", [])}


def search_versions(name: str) -> list[dict[str, Any]]:
    """Versions d'un modèle enregistré, tags aplatis, de la plus récente à la plus ancienne."""
    payload = _call("GET", "/model-versions/search", params={"filter": f"name = '{name}'"})
    versions = payload.get("model_versions", [])
    for mv in versions:
        mv["tags_dict"] = _tags(mv)
        mv["version_int"] = int(mv["version"])
    return sorted(versions, key=lambda mv: mv["version_int"], reverse=True)


def version_by_alias(name: str, alias: str) -> dict[str, Any] | None:
    response = requests.get(
        f"{config.MLFLOW_URL}{API}/registered-models/alias",
        params={"name": name, "alias": alias},
        timeout=config.HTTP_TIMEOUT,
    )
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        raise RuntimeError(f"mlflow alias -> HTTP {response.status_code} : {response.text[:300]}")
    mv = response.json()["model_version"]
    mv["tags_dict"] = _tags(mv)
    mv["version_int"] = int(mv["version"])
    return mv


def set_alias(name: str, alias: str, version: int) -> None:
    _call(
        "POST",
        "/registered-models/alias",
        json={"name": name, "alias": alias, "version": str(version)},
    )


def set_version_tag(name: str, version: int, key: str, value: str) -> None:
    _call(
        "POST",
        "/model-versions/set-tag",
        json={"name": name, "version": str(version), "key": key, "value": value},
    )


def run_metrics(run_id: str) -> dict[str, float]:
    payload = _call("GET", "/runs/get", params={"run_id": run_id})
    return {m["key"]: float(m["value"]) for m in payload["run"]["data"].get("metrics", [])}
