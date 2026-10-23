"""Normalisation des plaques : copie volontaire de la règle unique du backend (backend/app/core/plates.py).

Les deux paquets sont indépendants ; la règle tient en une ligne et doit rester identique.
"""

import re

_NOT_ALNUM = re.compile(r"[^A-Z0-9]")


def normalize_plate(text: str) -> str:
    return _NOT_ALNUM.sub("", text.upper())
