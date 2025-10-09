"""Centralized helpers for sanitizing contact payloads prior to persistence."""

from __future__ import annotations

from typing import Any, Mapping

from app.core.normalization import (
    normalize_country_code,
    normalize_international_phone,
    normalize_language_code,
    strip_to_none,
)


def sanitize_contact_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a sanitized copy of the contact payload.

    The function trims string values, removes empty strings, and normalizes
    well-known identifiers (phone numbers, countries, languages) so database
    records remain consistent regardless of the input source.
    """

    sanitized: dict[str, Any] = {}

    for key, value in payload.items():
        if isinstance(value, str):
            sanitized[key] = strip_to_none(value)
        else:
            sanitized[key] = value

    if "phone" in sanitized:
        sanitized["phone"] = normalize_international_phone(sanitized["phone"])

    for country_key in ("country", "country_iso"):
        if country_key in sanitized:
            sanitized[country_key] = normalize_country_code(sanitized[country_key])

    for language_key in ("language", "preferred_language"):
        if language_key in sanitized:
            sanitized[language_key] = normalize_language_code(sanitized[language_key])

    return sanitized
