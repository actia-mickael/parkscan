"""Types et validateurs partagés par les schémas."""

import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel

from app.core.plates import validate_plate

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if not _EMAIL_RE.match(value):
        raise ValueError("adresse e-mail invalide")
    return value


def check_plate(value: str) -> str:
    validate_plate(value)  # lève ValueError si implausible ; on conserve la saisie d'origine
    return value.strip()


EmailField = Annotated[str, AfterValidator(normalize_email)]
PlateField = Annotated[str, AfterValidator(check_plate)]


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int
