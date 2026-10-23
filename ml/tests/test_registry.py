"""Résolution des modèles : repli local, MLflow obligatoire, cache par version (MLflow simulé)."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from parkscan_ml.config import Settings
from parkscan_ml.registry import ModelRegistry


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    weights = tmp_path / "weights"
    weights.mkdir()
    (weights / "plate_detector.pt").write_bytes(b"plate")
    (weights / "brand_classifier.pth").write_bytes(b"brand")
    generic = tmp_path / "generic"
    generic.mkdir()
    (generic / "yolov8s.pt").write_bytes(b"vehicle")
    return Settings(
        _env_file=None,
        weights_dir=weights,
        generic_models_dir=generic,
        mlflow_cache_dir=tmp_path / "cache",
        **overrides,
    )


class FakeClient:
    def __init__(self, version: str = "3", fail: bool = False) -> None:
        self.version = version
        self.fail = fail

    def get_model_version_by_alias(self, name: str, alias: str) -> SimpleNamespace:
        if self.fail:
            raise ConnectionError("mlflow injoignable")
        assert alias == "production"
        return SimpleNamespace(
            version=self.version, run_id="run123", source=f"mlflow-artifacts:/1/run123/{name}"
        )


def test_local_when_mlflow_not_configured(tmp_path: Path) -> None:
    registry = ModelRegistry(make_settings(tmp_path, model_source="auto", mlflow_tracking_uri=""))
    assert registry.resolve().origin == "local"


def test_mlflow_required_without_uri(tmp_path: Path) -> None:
    registry = ModelRegistry(make_settings(tmp_path, model_source="mlflow", mlflow_tracking_uri=""))
    with pytest.raises(RuntimeError, match="ML_MLFLOW_TRACKING_URI"):
        registry.resolve()


def test_auto_falls_back_to_local_when_unreachable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = ModelRegistry(
        make_settings(tmp_path, model_source="auto", mlflow_tracking_uri="http://mlflow:5000")
    )
    monkeypatch.setattr(registry, "_mlflow_client", lambda: FakeClient(fail=True))
    assert registry.resolve().origin == "local"


def test_mlflow_strict_raises_when_unreachable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = ModelRegistry(
        make_settings(tmp_path, model_source="mlflow", mlflow_tracking_uri="http://mlflow:5000")
    )
    monkeypatch.setattr(registry, "_mlflow_client", lambda: FakeClient(fail=True))
    with pytest.raises(ConnectionError):
        registry.resolve()


def test_mlflow_resolution_downloads_once_per_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = make_settings(
        tmp_path, model_source="auto", mlflow_tracking_uri="http://mlflow:5000"
    )
    registry = ModelRegistry(settings)
    client = FakeClient(version="3")
    downloads: list[str] = []

    def fake_download(uri: str, target: Path) -> None:
        downloads.append(uri)
        model_dir = target / "model"
        model_dir.mkdir(parents=True, exist_ok=True)
        name = "checkpoint.pth" if "brand" in uri else "plate_detector.pt"
        (model_dir / name).write_bytes(b"x")

    monkeypatch.setattr(registry, "_mlflow_client", lambda: client)
    monkeypatch.setattr(registry, "_download", fake_download)

    sources = registry.resolve()
    assert sources.origin == "mlflow"
    cache = settings.mlflow_cache_dir
    assert (
        sources.brand_classifier == cache / "brand_classifier" / "v3" / "model" / "checkpoint.pth"
    )
    assert sources.plate_detector == cache / "plate_detector" / "v3" / "model" / "plate_detector.pt"
    assert sources.labels["brand_classifier"] == "mlflow:brand_classifier@production:v3"
    assert sources.details["plate_detector"]["run_id"] == "run123"
    assert sorted(downloads) == ["models:/brand_classifier/3", "models:/plate_detector/3"]

    registry.resolve()
    assert len(downloads) == 2, "même version : servie depuis le cache"

    client.version = "4"
    assert registry.resolve().labels["brand_classifier"].endswith(":v4")
    assert len(downloads) == 4, "nouvelle version : téléchargée"
