"""Routing service utilities with consent awareness."""

from .preferences import (
    ContactPreferenceResolver,
    ContactRoutingPreferences,
    ContactOptOutError,
    MultiChannelConsentResolver,
)

__all__ = [
    "ContactPreferenceResolver",
    "ContactRoutingPreferences",
    "ContactOptOutError",
    "MultiChannelConsentResolver",
]
