"""Normalisation des plaques : LA règle unique, partagée par le backend, l'agent de bord et le seed."""

import re

_NOT_ALNUM = re.compile(r"[^A-Z0-9]")
MIN_PLATE_LENGTH = 4
MAX_PLATE_LENGTH = 12


def normalize_plate(text: str) -> str:
    """Majuscules, puis suppression de tout caractère hors A-Z et 0-9 ("ab-123 cd" → "AB123CD")."""
    return _NOT_ALNUM.sub("", text.upper())


def validate_plate(text: str) -> str:
    """Retourne la forme normalisée ou lève ValueError si la plaque n'est pas plausible."""
    normalized = normalize_plate(text)
    if not MIN_PLATE_LENGTH <= len(normalized) <= MAX_PLATE_LENGTH:
        raise ValueError(
            f"plaque invalide : {MIN_PLATE_LENGTH} à {MAX_PLATE_LENGTH} caractères alphanumériques attendus"
        )
    return normalized
