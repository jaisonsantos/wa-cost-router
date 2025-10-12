"""Routing service utilities with consent awareness."""

from .preferences import (
    ContactPreferenceResolver,
    ContactRoutingPreferences,
    ContactOptOutError,
    MultiChannelConsentResolver,
)
from .policies import RoutingPolicyService, RoutingPolicyViolation

__all__ = [
    "ContactPreferenceResolver",
    "ContactRoutingPreferences",
    "ContactOptOutError",
    "MultiChannelConsentResolver",
    "RoutingPolicyService",
    "RoutingPolicyViolation",
]
