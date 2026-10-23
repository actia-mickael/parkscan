"""Recadrages JPEG (Pillow) pour les crops plaque et véhicule."""

from io import BytesIO

from PIL import Image


def crop_jpeg(data: bytes, bbox: list[int], quality: int = 90) -> bytes:
    with Image.open(BytesIO(data)) as image:
        image = image.convert("RGB")
        x1, y1, x2, y2 = bbox
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(image.width, x2), min(image.height, y2)
        if x2 <= x1 or y2 <= y1:
            raise ValueError("zone de recadrage vide")
        out = BytesIO()
        image.crop((x1, y1, x2, y2)).save(out, format="JPEG", quality=quality)
        return out.getvalue()
