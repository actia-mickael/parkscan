from httpx import AsyncClient

from parkscan_ml.config import get_settings
from parkscan_ml.main import app


async def test_infer_returns_contract(client: AsyncClient, jpeg_bytes: bytes) -> None:
    response = await client.post(
        "/infer",
        files={"image": ("car.jpg", jpeg_bytes, "image/jpeg")},
        data={"det_threshold": "0.4", "return_annotated": "true"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["plates"][0]["text_norm"] == "AB123CD"
    assert body["plates"][0]["ocr_conf"] == 0.93
    assert body["vehicle"]["class_name"] == "car"
    assert body["brand"]["label"] == "renault"
    assert body["conditions"]["lighting"] in {"night", "low", "medium", "day"}
    assert body["image_size"] == [240, 320]
    assert body["model_versions"]["ocr"] == "fake:ocr"
    assert body["annotated_image_b64"]


async def test_infer_without_branch2(client: AsyncClient, jpeg_bytes: bytes) -> None:
    response = await client.post(
        "/infer",
        files={"image": ("car.jpg", jpeg_bytes, "image/jpeg")},
        data={"run_branch2": "false"},
    )
    assert response.status_code == 200
    assert response.json()["vehicle"] is None
    assert response.json()["brand"] is None
    assert response.json()["annotated_image_b64"] is None


async def test_infer_rejects_unreadable_image(client: AsyncClient) -> None:
    response = await client.post(
        "/infer", files={"image": ("x.jpg", b"not an image", "image/jpeg")}
    )
    assert response.status_code == 400


async def test_health_and_models(client: AsyncClient) -> None:
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    models = await client.get("/models")
    assert models.status_code == 200
    assert models.json()["labels"] == ["peugeot", "renault"]
    assert models.json()["models"]["brand_classifier"]["details"] == {"arch": "fake"}


async def test_health_reports_missing_models(client: AsyncClient) -> None:
    app.state.pipeline = None
    assert (await client.get("/health")).status_code == 503
    assert (
        await client.post("/infer", files={"image": ("x.jpg", b"0", "image/jpeg")})
    ).status_code == 503


async def test_reload_requires_internal_token_and_swaps_pipeline(client: AsyncClient) -> None:
    denied = await client.post("/models/reload")
    assert denied.status_code == 401
    token = get_settings().internal_token
    before = app.state.pipeline
    ok = await client.post("/models/reload", headers={"X-Internal-Token": token})
    assert ok.status_code == 200, ok.text
    assert app.state.registry.loads == 1
    assert app.state.pipeline is not before
