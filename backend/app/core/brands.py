"""Forme canonique des marques et règle d'écart entre marque prédite et marque déclarée."""

import re
import unicodedata

_NOT_ALNUM = re.compile(r"[^a-z0-9]")
OTHER = "other"


def normalize_label(label: str) -> str:
    """Minuscules, accents retirés, tout sauf lettres et chiffres supprimé ("Mercedes-Benz" → "mercedesbenz")."""
    ascii_label = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
    return _NOT_ALNUM.sub("", ascii_label.lower())


def build_alias_map(brands: list[tuple[str, list[str]]]) -> dict[str, str]:
    """{forme normalisée du slug ou d'un alias: slug}, à partir du référentiel."""
    alias_map: dict[str, str] = {}
    for slug, aliases in brands:
        alias_map[normalize_label(slug)] = slug
        for alias in aliases:
            alias_map[normalize_label(alias)] = slug
    return alias_map


def canonical(label: str | None, alias_map: dict[str, str]) -> str | None:
    if not label:
        return None
    normalized = normalize_label(label)
    return alias_map.get(normalized, normalized) or None


def is_mismatch(
    predicted: str | None,
    confidence: float | None,
    declared: str | None,
    threshold: float,
    alias_map: dict[str, str],
) -> bool:
    """Écart ssi prédite ≠ déclarée (formes canoniques), confiance ≥ seuil, et prédite ≠ 'other'."""
    pred = canonical(predicted, alias_map)
    decl = canonical(declared, alias_map)
    if pred is None or decl is None or confidence is None:
        return False
    if confidence < threshold or pred == OTHER:
        return False
    return pred != decl
