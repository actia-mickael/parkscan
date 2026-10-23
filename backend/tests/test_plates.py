import pytest

from app.core.plates import normalize_plate, validate_plate


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("AB-123-CD", "AB123CD"),
        ("ab 123 cd", "AB123CD"),
        ("51-A 77.529", "51A77529"),
        ("  zz-001-zz ", "ZZ001ZZ"),
    ],
)
def test_normalize_plate(raw: str, expected: str) -> None:
    assert normalize_plate(raw) == expected


def test_validate_plate_rejects_implausible_values() -> None:
    with pytest.raises(ValueError):
        validate_plate("A-1")
    with pytest.raises(ValueError):
        validate_plate("ABCDEFGHIJKLMNOP")
    assert validate_plate("AB-123-CD") == "AB123CD"
