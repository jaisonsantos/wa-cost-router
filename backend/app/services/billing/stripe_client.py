"""Utilities to interact with Stripe's SDK."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import stripe

from app.core.config import settings


class StripeConfigurationError(RuntimeError):
    """Raised when Stripe configuration is missing or invalid."""


class StripeGateway:
    """Thin wrapper around :mod:`stripe` operations used by the API."""

    def __init__(self, secret_key: str) -> None:
        if not secret_key:
            raise StripeConfigurationError("STRIPE_SECRET_KEY is not configured")
        self._client = stripe.StripeClient(secret_key)

    @property
    def client(self) -> stripe.StripeClient:
        return self._client

    def create_customer(self, **kwargs: Any) -> Any:
        return self._client.customers.create(**kwargs)

    def create_checkout_session(self, **kwargs: Any) -> Any:
        return self._client.checkout.sessions.create(**kwargs)

    def create_billing_portal_session(self, **kwargs: Any) -> Any:
        return self._client.billing_portal.sessions.create(**kwargs)

    def retrieve_subscription(self, subscription_id: str) -> Any:
        return self._client.subscriptions.retrieve(subscription_id)

    def retrieve_payment_method(self, payment_method_id: str) -> Any:
        return self._client.payment_methods.retrieve(payment_method_id)

    def retrieve_invoice(self, invoice_id: str) -> Any:
        return self._client.invoices.retrieve(invoice_id)

    def create_usage_record(
        self,
        *,
        subscription_item_id: str,
        quantity: int,
        timestamp: int,
        action: str = "set",
        idempotency_key: str | None = None,
    ) -> Any:
        payload: dict[str, Any] = {
            "subscription_item": subscription_item_id,
            "quantity": quantity,
            "timestamp": timestamp,
            "action": action,
        }
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        return self._client.usage_records.create(**payload)


@lru_cache(maxsize=1)
def get_stripe_gateway() -> StripeGateway:
    """Return a cached :class:`StripeGateway` instance."""

    return StripeGateway(settings.STRIPE_SECRET_KEY)


def verify_webhook_event(payload: bytes, signature: str | None) -> Any:
    """Validate a Stripe webhook payload and return the parsed event."""

    secret = settings.STRIPE_WEBHOOK_SECRET
    if not secret:
        raise StripeConfigurationError("STRIPE_WEBHOOK_SECRET is not configured")
    if not signature:
        raise ValueError("Missing Stripe-Signature header")
    return stripe.Webhook.construct_event(payload=payload, sig_header=signature, secret=secret)
