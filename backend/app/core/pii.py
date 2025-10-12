"""Utilities for masking personally identifiable information (PII).

This module centralises the logic used across the application to ensure that
sensitive payloads such as template variables and provider responses do not
persist or expose raw telephone numbers, email addresses or credentials.  The
helpers operate on nested structures and always return sanitized copies so the
callers can continue working with the original payload when necessary (e.g.
to send data to an external provider).
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

MASK_TOKEN = "***redacted***"

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_WORD_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


@dataclass(frozen=True)
class _SanitizationContext:
    parent_key: str | None = None


_TOKEN_EXACT_MATCHES = {
    "access_token",
    "auth_token",
    "refresh_token",
    "token",
    "password",
    "secret",
    "client_secret",
    "client_secret_id",
    "api_key",
    "access_key",
    "secret_key",
    "signature",
    "authorization",
    "credentials",
    "credential",
    "bearer",
}

_TOKEN_PARTIALS = {"token", "secret", "password", "credential"}
_EMAIL_KEYS = {"email"}
_PHONE_KEYS = {"phone", "msisdn", "wa_id", "channel_address"}


def mask_phone(value: str) -> str:
    """Return a masked representation of ``value``.

    Only the last two digits of the numeric sequence are kept in clear text and
    a leading ``+`` is preserved when present. Non-numeric characters other than
    ``+`` are stripped so that the masked value can be compared consistently in
    tests and logs.
    """

    if not isinstance(value, str):
        return MASK_TOKEN

    candidate = value.strip()
    if not candidate:
        return MASK_TOKEN

    prefix = "+" if candidate.startswith("+") else ""
    digits = re.sub(r"\D", "", candidate)
    if not digits:
        return MASK_TOKEN

    if len(digits) <= 2:
        masked_digits = "*" * len(digits)
    else:
        masked_digits = "*" * (len(digits) - 2) + digits[-2:]

    return f"{prefix}{masked_digits}"


def mask_email(value: str) -> str:
    """Return a masked representation of ``value``.

    The first character of the local part and the domain are kept and the rest
    is replaced with wildcards. Invalid email addresses result in
    ``MASK_TOKEN``.
    """

    if not isinstance(value, str):
        return MASK_TOKEN

    candidate = value.strip()
    if not candidate or not _EMAIL_PATTERN.match(candidate):
        return MASK_TOKEN

    local, _, domain = candidate.partition("@")
    local_mask = (local[0] + "***") if len(local) > 1 else "***"

    domain_root, _, domain_suffix = domain.partition(".")
    if domain_suffix:
        root_mask = (domain_root[0] + "***") if len(domain_root) > 1 else "***"
        domain_mask = f"{root_mask}.{domain_suffix}"
    else:
        domain_mask = (domain_root[0] + "***") if len(domain_root) > 1 else "***"

    return f"{local_mask}@{domain_mask}"


def mask_contact_point(value: str | None, *, channel: str | None = None) -> str | None:
    """Mask a contact value based on the communication channel when available."""

    if value is None:
        return None

    if channel:
        normalized = channel.strip().lower()
        if normalized in {"email"}:
            return mask_email(value)
        if normalized in {"whatsapp", "sms"}:
            return mask_phone(value)

    # Fallback to best-effort inference when the channel is unknown.
    if _looks_like_email(value):
        return mask_email(value)
    if _looks_like_phone(value):
        return mask_phone(value)
    return value


def sanitize_template_variables(payload: Any) -> Any:
    """Sanitize template variables before persisting them."""

    return _sanitize_payload(payload, _SanitizationContext())


def sanitize_provider_payload(payload: Any) -> Any:
    """Sanitize provider responses before persisting them."""

    return _sanitize_payload(payload, _SanitizationContext())


def _sanitize_payload(value: Any, context: _SanitizationContext) -> Any:
    if isinstance(value, dict):
        sanitized: dict[Any, Any] = {}
        for key, item in value.items():
            lowered_key = str(key).lower()
            if _is_sensitive_key(lowered_key):
                sanitized[key] = MASK_TOKEN
                continue
            sanitized[key] = _sanitize_payload(item, _SanitizationContext(parent_key=lowered_key))
        return sanitized

    if isinstance(value, list):
        return [_sanitize_payload(item, context) for item in value]

    if isinstance(value, tuple):
        return tuple(_sanitize_payload(item, context) for item in value)

    if isinstance(value, str):
        return _mask_string(value, context.parent_key)

    return value


def _mask_string(value: str, parent_key: str | None) -> str:
    candidate = value.strip()
    lowered_parent = (parent_key or "").lower()

    if lowered_parent in {"job_id", "rule_id", "provider_id", "org_id", "message_event_id"}:
        return value

    if _looks_like_email(candidate) or lowered_parent in _EMAIL_KEYS:
        return mask_email(candidate)

    if _looks_like_phone(candidate) or lowered_parent in _PHONE_KEYS:
        return mask_phone(candidate)

    if lowered_parent and _contains_token_hint(lowered_parent):
        return MASK_TOKEN

    return value


def _is_sensitive_key(key: str) -> bool:
    if key in _TOKEN_EXACT_MATCHES:
        return True

    return _contains_token_hint(key)


def _contains_token_hint(value: str) -> bool:
    words = _split_words(value)
    return any(word in _TOKEN_PARTIALS for word in words)


def _split_words(value: str) -> Iterable[str]:
    return _WORD_PATTERN.findall(value.lower())


def _looks_like_email(value: str) -> bool:
    return bool(_EMAIL_PATTERN.match(value.strip()))


def _looks_like_phone(value: str) -> bool:
    candidate = value.strip()
    if not candidate:
        return False

    digits = re.sub(r"\D", "", candidate)
    if len(digits) < 6:
        return False

    digit_ratio = len(digits) / len(candidate)
    if digit_ratio < 0.6:
        return False

    starts_with_valid = candidate[0] == "+" or candidate[0].isdigit()
    return starts_with_valid

