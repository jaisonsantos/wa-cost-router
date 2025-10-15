from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
from stripe import error as stripe_error

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.models import BillingStatusEnum, BillingSubscription, Organization, User
from app.services.billing import (
    StripeConfigurationError,
    get_stripe_gateway,
    verify_webhook_event,
)
from app.workers.billing_usage import enqueue_billing_usage_sync

router = APIRouter()


class CheckoutRequest(BaseModel):
    price_id: str
    success_url: HttpUrl
    cancel_url: HttpUrl


class CheckoutResponse(BaseModel):
    checkout_url: HttpUrl


class BillingSummaryResponse(BaseModel):
    plan_name: str | None = None
    plan_status: str = "inactive"
    price_amount_minor: int | None = None
    price_currency: str | None = None
    next_billing_at: datetime | None = None
    cancel_at_period_end: bool = False
    payment_method_brand: str | None = None
    payment_method_last4: str | None = None
    message_quota: int | None = None
    message_usage: int | None = None
    latest_invoice_url: HttpUrl | None = None
    price_id: str | None = None


class UsageSyncTriggerResponse(BaseModel):
    job_id: str
    status: str


def _as_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    for attr in ("to_dict_recursive", "to_dict"):
        method = getattr(value, attr, None)
        if callable(method):
            result = method()
            if isinstance(result, dict):
                return result
    return None


def _parse_uuid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _get_org_user(db: Session, org_id: uuid.UUID, user_id: uuid.UUID) -> tuple[Organization, User]:
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return org, user


def _get_subscription_by_org(db: Session, org_id: uuid.UUID) -> BillingSubscription | None:
    return db.query(BillingSubscription).filter(BillingSubscription.org_id == org_id).first()


def _get_subscription_by_customer(db: Session, customer_id: str) -> BillingSubscription | None:
    return (
        db.query(BillingSubscription)
        .filter(BillingSubscription.stripe_customer_id == customer_id)
        .first()
    )


def _ensure_subscription(
    db: Session,
    *,
    org_id: uuid.UUID,
    customer_id: str,
) -> BillingSubscription:
    subscription = _get_subscription_by_org(db, org_id)
    if subscription:
        if subscription.stripe_customer_id != customer_id and customer_id:
            subscription.stripe_customer_id = customer_id
        return subscription

    if not customer_id:
        raise HTTPException(status_code=400, detail="Missing Stripe customer id")

    subscription = BillingSubscription(
        org_id=org_id,
        stripe_customer_id=customer_id,
        status=BillingStatusEnum.incomplete,
    )
    db.add(subscription)
    return subscription


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout_session(
    payload: CheckoutRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    try:
        gateway = get_stripe_gateway()
    except StripeConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    org, user = _get_org_user(db, current_user["org_id"], current_user["user_id"])

    subscription = _get_subscription_by_org(db, org.id)
    customer_id = subscription.stripe_customer_id if subscription else None

    if not customer_id:
        try:
            customer = gateway.create_customer(
                email=user.email,
                name=org.name,
                metadata={"org_id": str(org.id), "org_name": org.name},
            )
        except stripe_error.StripeError as exc:  # pragma: no cover
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        customer_id = customer.id
        subscription = _ensure_subscription(db, org_id=org.id, customer_id=customer_id)
        db.commit()
        db.refresh(subscription)

    try:
        session = gateway.create_checkout_session(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": payload.price_id, "quantity": 1}],
            success_url=str(payload.success_url),
            cancel_url=str(payload.cancel_url),
            automatic_tax={"enabled": True},
            metadata={"org_id": str(org.id), "price_id": payload.price_id},
            subscription_data={"metadata": {"org_id": str(org.id)}},
        )
    except stripe_error.StripeError as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if subscription:
        subscription.price_id = payload.price_id
        db.commit()

    return CheckoutResponse(checkout_url=session.url)


@router.get("/summary", response_model=BillingSummaryResponse)
def get_billing_summary(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BillingSummaryResponse:
    subscription = _get_subscription_by_org(db, current_user["org_id"])
    if not subscription:
        return BillingSummaryResponse()

    payment_method = subscription.default_payment_method or {}
    latest_invoice_url = subscription.latest_invoice_url

    return BillingSummaryResponse(
        plan_name=subscription.plan_nickname,
        plan_status=subscription.status.value if subscription.status else "inactive",
        price_amount_minor=subscription.amount_minor,
        price_currency=subscription.currency,
        next_billing_at=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        payment_method_brand=payment_method.get("brand"),
        payment_method_last4=payment_method.get("last4"),
        message_quota=subscription.message_quota,
        message_usage=subscription.message_usage,
        latest_invoice_url=latest_invoice_url,
        price_id=subscription.price_id,
    )


def _update_from_subscription_payload(
    db: Session,
    payload: dict[str, Any],
    *,
    org_id: uuid.UUID | None,
    customer_id: str | None,
) -> None:
    if not customer_id:
        return

    if org_id:
        subscription = _ensure_subscription(db, org_id=org_id, customer_id=customer_id)
    else:
        subscription = _get_subscription_by_customer(db, customer_id)

    if not subscription:
        return

    subscription.stripe_subscription_id = payload.get("id") or subscription.stripe_subscription_id

    status_value = payload.get("status")
    if isinstance(status_value, str):
        try:
            subscription.status = BillingStatusEnum(status_value)
        except ValueError:
            subscription.status = BillingStatusEnum.incomplete

    subscription.cancel_at_period_end = bool(payload.get("cancel_at_period_end"))

    period_end = payload.get("current_period_end")
    if isinstance(period_end, (int, float)):
        subscription.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)

    items = payload.get("items", {})
    item_list = items.get("data") if isinstance(items, dict) else None
    if isinstance(item_list, list) and item_list:
        price = item_list[0].get("price", {})
        if isinstance(price, dict):
            subscription.price_id = price.get("id") or subscription.price_id
            subscription.currency = price.get("currency") or subscription.currency
            unit_amount = price.get("unit_amount")
            if isinstance(unit_amount, int):
                subscription.amount_minor = unit_amount
            nickname = price.get("nickname")
            if isinstance(nickname, str):
                subscription.plan_nickname = nickname
            metadata = price.get("metadata")
            if isinstance(metadata, dict):
                quota = metadata.get("message_quota")
                if quota is not None:
                    try:
                        subscription.message_quota = int(quota)
                    except (TypeError, ValueError):
                        pass
        item_id = item_list[0].get("id")
        if isinstance(item_id, str):
            subscription.stripe_subscription_item_id = item_id
        quantity = item_list[0].get("quantity")
        if isinstance(quantity, int):
            subscription.message_usage = quantity

    default_payment_method = payload.get("default_payment_method")
    if isinstance(default_payment_method, dict):
        card = default_payment_method.get("card")
        if isinstance(card, dict):
            brand = card.get("brand")
            last4 = card.get("last4")
            payment_info: dict[str, Any] = {}
            if isinstance(brand, str):
                payment_info["brand"] = brand
            if isinstance(last4, str):
                payment_info["last4"] = last4
            if payment_info:
                subscription.default_payment_method = payment_info

    db.commit()


def _handle_invoice_paid(db: Session, payload: dict[str, Any]) -> None:
    customer_id = payload.get("customer")
    if not isinstance(customer_id, str):
        return
    subscription = _get_subscription_by_customer(db, customer_id)
    if not subscription:
        return
    lines = payload.get("lines", {})
    line_items = lines.get("data") if isinstance(lines, dict) else None
    if isinstance(line_items, list):
        for line in line_items:
            if not isinstance(line, dict):
                continue
            if line.get("type") != "subscription":
                continue
            quantity = line.get("quantity")
            if isinstance(quantity, int):
                subscription.message_usage = quantity
    hosted_invoice_url = payload.get("hosted_invoice_url")
    if isinstance(hosted_invoice_url, str):
        subscription.latest_invoice_url = hosted_invoice_url
    status_value = payload.get("status")
    if isinstance(status_value, str):
        try:
            subscription.status = BillingStatusEnum(status_value)
        except ValueError:
            pass
    db.commit()


@router.post("/webhook")
async def handle_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")

    try:
        event = verify_webhook_event(payload, signature)
    except (StripeConfigurationError, ValueError, stripe_error.SignatureVerificationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Normaliza o objeto Event/Stripe para dicts
    event_payload = _as_dict(event) or {}
    event_type = event_payload.get("type")

    data_payload = _as_dict(event_payload.get("data")) or {}
    data_object = _as_dict(data_payload.get("object")) or {}

    metadata = _as_dict(data_object.get("metadata")) or {}
    org_id = _parse_uuid(metadata.get("org_id"))
    customer_id = data_object.get("customer") if isinstance(data_object.get("customer"), str) else None

    if event_type == "checkout.session.completed":
        subscription_id = data_object.get("subscription")
        if customer_id and org_id:
            subscription = _ensure_subscription(db, org_id=org_id, customer_id=customer_id)
            subscription.stripe_subscription_id = subscription_id or subscription.stripe_subscription_id
            if data_object.get("status") == "complete":
                subscription.status = BillingStatusEnum.active
            price_id = metadata.get("price_id")
            if isinstance(price_id, str):
                subscription.price_id = price_id
            db.commit()

    elif event_type in {"customer.subscription.updated", "customer.subscription.created"}:
        _update_from_subscription_payload(db, data_object, org_id=org_id, customer_id=customer_id)

    elif event_type == "customer.subscription.deleted":
        subscription = None
        if org_id and customer_id:
            subscription = _ensure_subscription(db, org_id=org_id, customer_id=customer_id)
        elif customer_id:
            subscription = _get_subscription_by_customer(db, customer_id)
        if subscription:
            subscription.status = BillingStatusEnum.canceled
            subscription.cancel_at_period_end = True
            db.commit()

    elif event_type in {"invoice.paid", "invoice.payment_succeeded"}:
        _handle_invoice_paid(db, data_object)

    return {"received": "ok"}


@router.post("/usage/sync", response_model=UsageSyncTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_usage_sync(
    current_user: dict = Depends(get_current_user),
) -> UsageSyncTriggerResponse:
    if not settings.BILLING_USAGE_SYNC_ENABLED or not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing usage sync is disabled",
        )

    job_id = enqueue_billing_usage_sync()
    return UsageSyncTriggerResponse(job_id=job_id, status="enqueued")
