"""Doublures du service ML et du stockage pour les tests : aucun réseau, aucun modèle."""

from app.schemas.ml import MlBrand, MlInferResult, MlPlate, MlVehicle
from app.services.ml_client import MlUnavailableError


def ml_result(
    plate: str | None = "AB-123-CD",
    ocr_conf: float = 0.95,
    brand: str | None = "renault",
    brand_conf: float = 0.9,
) -> MlInferResult:
    plates = (
        [
            MlPlate(
                bbox=[10, 10, 120, 40],
                text=plate,
                text_norm=plate.replace("-", ""),
                ocr_conf=ocr_conf,
                det_conf=0.8,
            )
        ]
        if plate
        else []
    )
    return MlInferResult(
        plates=plates,
        vehicle=MlVehicle(bbox=[0, 0, 300, 200], class_name="car", conf=0.9),
        brand=MlBrand(
            label=brand,
            conf=brand_conf,
            top3=[(brand, brand_conf), ("peugeot", 0.05), ("ford", 0.02)],
        )
        if brand
        else None,
        conditions={
            "brightness": 120.0,
            "lighting": "medium",
            "blur_score": 800.0,
            "blur": "sharp",
        },
        timings_ms={"total": 250.0},
        model_versions={
            "plate_detector": "fake",
            "ocr": "fake",
            "vehicle_detector": "fake",
            "brand_classifier": "fake",
        },
        image_size=[240, 320],
    )


class FakeMlClient:
    def __init__(self) -> None:
        self.result: MlInferResult = ml_result()
        self.unavailable = False
        self.calls = 0

    async def infer(self, image: bytes, **_: object) -> MlInferResult:
        self.calls += 1
        if self.unavailable:
            raise MlUnavailableError("simulé")
        return self.result

    async def health(self) -> bool:
        return not self.unavailable

    async def reload(self) -> dict:
        return {}

    async def aclose(self) -> None:
        return None


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_bytes(
        self, bucket: str, key: str, data: bytes, content_type: str = "image/jpeg"
    ) -> None:
        self.objects[(bucket, key)] = data

    def copy(self, src_bucket: str, src_key: str, dst_bucket: str, dst_key: str) -> None:
        self.objects[(dst_bucket, dst_key)] = self.objects[(src_bucket, src_key)]

    def exists(self, bucket: str, key: str) -> bool:
        return (bucket, key) in self.objects

    def presigned_get_url(self, bucket: str, key: str, expires_in: int) -> str:
        return f"http://storage.test/{bucket}/{key}?expires={expires_in}"

    def check(self) -> bool:
        return True


def jpeg_bytes(width: int = 320, height: int = 240) -> bytes:
    """Une vraie image JPEG (gris uni) : les recadrages par zone ont de quoi travailler."""
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (width, height), (128, 128, 128)).save(buffer, format="JPEG")
    return buffer.getvalue()
