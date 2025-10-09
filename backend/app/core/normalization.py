"""Utility helpers for normalizing user supplied identifiers."""

from __future__ import annotations

import re
from typing import Any

_PHONE_REGEX = re.compile(r"^\+[1-9]\d{7,14}$")
_COUNTRY_REGEX = re.compile(r"^[A-Z]{2}$")
_LANGUAGE_REGEX = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})?$")


def strip_to_none(value: Any) -> Any:
    """Return the input stripped of whitespace or ``None`` when empty."""

    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def normalize_international_phone(value: str | None) -> str | None:
    """Normalize and validate international phone numbers.

    Numbers are converted to the canonical E.164 representation (``+`` followed by
    8-15 digits). Common separators such as spaces, hyphens and parentheses are
    ignored during normalization. Values starting with ``00`` are treated as a
    malformed international prefix and converted to ``+``.
    """

    if value is None:
        return None

    sanitized = value.strip()
    if not sanitized:
        return None

    # Remove common separators to make it easier for users to send formatted numbers.
    sanitized = re.sub(r"[\s\-()]+", "", sanitized)

    if sanitized.startswith("00"):
        sanitized = "+" + sanitized[2:]

    if not sanitized.startswith("+"):
        raise ValueError("phone numbers must include country code in E.164 format")

    digits = "+" + re.sub(r"[^0-9]", "", sanitized[1:])

    if not _PHONE_REGEX.fullmatch(digits):
        raise ValueError("phone numbers must follow the E.164 format (e.g. +15551234567)")

    return digits


def normalize_country_code(value: str | None) -> str | None:
    """Normalize ISO country identifiers to upper-case alpha-2 codes."""

    if value is None:
        return None

    stripped = value.strip()
    if not stripped:
        return None

    normalized = stripped.upper()
    if not _COUNTRY_REGEX.fullmatch(normalized):
        raise ValueError("country codes must be ISO 3166-1 alpha-2 values")

    return normalized


def normalize_language_code(value: str | None) -> str | None:
    """Normalize BCP 47 language tags to a canonical lower-case form."""

    if value is None:
        return None

    stripped = value.strip()
    if not stripped:
        return None

    normalized = stripped.replace("_", "-").lower()
    if not _LANGUAGE_REGEX.fullmatch(normalized):
        raise ValueError("language codes must follow the BCP 47 format (e.g. en, pt-br)")

    return normalized
