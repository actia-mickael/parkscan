"""Identifiants lisibles (slugs) à partir de noms libres."""

import re
import unicodedata


def slugify(value: str, *, max_length: int = 60, fallback: str = "item") -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug[:max_length].strip("-") or fallback
