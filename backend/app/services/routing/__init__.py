"""Routing service utilities with consent awareness."""

from .preferences import (
    ContactPreferenceResolver,
    ContactRoutingPreferences,
    ContactOptOutError,
)

__all__ = [
    "ContactPreferenceResolver",
    "ContactRoutingPreferences",
    "ContactOptOutError",
]
