"""Tests for the phone E.164 normalizer."""

from __future__ import annotations

import pytest
from app.enrichment.phone import to_e164


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("04 72 00 11 22", "+33472001122"),
        ("0472001122", "+33472001122"),
        ("+33 4 72 00 11 22", "+33472001122"),
        ("01.23.45.67.89", "+33123456789"),
        (None, None),
        ("", None),
        ("not a phone", None),
        ("12", None),
    ],
)
def test_to_e164(raw: str | None, expected: str | None) -> None:
    assert to_e164(raw) == expected
