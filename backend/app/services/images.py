"""Recadrages JPEG (Pillow) pour les crops plaque et véhicule, floutage de la plaque (ADR-011)."""

from io import BytesIO

from PIL import Image, ImageFilter


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


def plate_rect_in_vehicle(
    plate_bbox: list[int] | None, vehicle_bbox: list[int] | None
) -> list[int] | None:
    """Zone de la plaque exprimée dans le repère du crop véhicule (None si inconnue ou vide)."""
    if not plate_bbox or not vehicle_bbox:
        return None
    vx1, vy1, vx2, vy2 = vehicle_bbox
    px1, py1, px2, py2 = plate_bbox
    rect = [
        max(0, px1 - vx1),
        max(0, py1 - vy1),
        min(vx2 - vx1, px2 - vx1),
        min(vy2 - vy1, py2 - vy1),
    ]
    return rect if rect[2] > rect[0] and rect[3] > rect[1] else None


def blur_region_jpeg(
    data: bytes, rect: list[int], margin: float = 0.15, quality: int = 90
) -> bytes:
    """Floute (gaussien) une zone, élargie d'une marge, et renvoie le JPEG résultant."""
    with Image.open(BytesIO(data)) as image:
        image = image.convert("RGB")
        x1, y1, x2, y2 = rect
        width, height = x2 - x1, y2 - y1
        if width <= 0 or height <= 0:
            return data
        mx, my = int(width * margin), int(height * margin)
        box = (
            max(0, x1 - mx),
            max(0, y1 - my),
            min(image.width, x2 + mx),
            min(image.height, y2 + my),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            return data
        radius = max(4, min(width, height) // 3)
        image.paste(image.crop(box).filter(ImageFilter.GaussianBlur(radius=radius)), box)
        out = BytesIO()
        image.save(out, format="JPEG", quality=quality)
        return out.getvalue()
