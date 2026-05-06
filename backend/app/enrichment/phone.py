"""Phone normalization to E.164 (default country FR)."""

from __future__ import annotations

import phonenumbers


def to_e164(raw: str | None, default_region: str = "FR") -> str | None:
    """Return the E.164 representation of a phone number, or ``None``."""
    if not raw:
        return None
    try:
        parsed = phonenumbers.parse(raw, default_region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
