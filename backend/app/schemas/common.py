"""Types et validateurs partagés par les schémas."""

import re
from typing import Annotated

from pydantic import AfterValidator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if not _EMAIL_RE.match(value):
        raise ValueError("adresse e-mail invalide")
    return value


EmailField = Annotated[str, AfterValidator(normalize_email)]
