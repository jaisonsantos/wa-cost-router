"""RQ worker that reconciles local invoices against Stripe."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import redis
from rq import Queue
from sqlalchemy.orm import Session
from stripe import error as stripe_error

from app.core.config import settings
from app.core.database import SessionLocal
from app.metrics import record_billing_reconcile_drift
from app.models.models import BillingInvoice
from app.services.billing import StripeConfigurationError, get_stripe_gateway


logger = logging.getLogger(__name__)

QUEUE_NAME = "billing_reconcile"


def get_queue(connection: Optional[redis.Redis] = None) -> Queue:
    conn = connection or redis.from_url(settings.REDIS_URL)
    return Queue(QUEUE_NAME, connection=conn)


def enqueue_billing_reconcile(*, since: datetime | None = None, until: datetime | None = None) -> str:
    job = get_queue().enqueue(
        process_billing_reconciliation,
        kwargs={"since": since, "until": until},
    )
    return job.id


def _as_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dict__"):
        return {k: v for k, v in vars(value).items() if not k.startswith("_")}
    for attr in ("to_dict_recursive", "to_dict"):
        method = getattr(value, attr, None)
        if callable(method):
            result = method()
            if isinstance(result, dict):
                return result
    return None


def _to_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_tax_amount(payload: dict[str, Any]) -> int:
    total_details = _as_dict(payload.get("total_details")) or {}
    amount_tax = _to_int(total_details.get("amount_tax"))
    if amount_tax is not None:
        return amount_tax

    tax_amounts = payload.get("total_tax_amounts")
    if isinstance(tax_amounts, list):
        accumulated = 0
        has_value = False
        for item in tax_amounts:
            item_dict = _as_dict(item) or {}
            amount = _to_int(item_dict.get("amount"))
            if amount is not None:
                accumulated += amount
                has_value = True
        if has_value:
            return accumulated

    direct_tax = _to_int(payload.get("tax")) or _to_int(payload.get("amount_tax"))
    return direct_tax or 0


def _calculate_drift(local_amount: int | None, remote_amount: int | None) -> float:
    if remote_amount in (None, 0):
        if local_amount in (None, 0):
            return 0.0
        return 100.0
    return abs((local_amount or 0) - (remote_amount or 0)) / abs(remote_amount) * 100


def process_billing_reconciliation(
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    db_session: Session | None = None,
) -> dict[str, Any]:
    try:
        gateway = get_stripe_gateway()
    except StripeConfigurationError:
        logger.info(
            "Skipping billing reconciliation because Stripe is not configured",
            extra={"event": "billing_reconcile_skipped", "reason": "stripe_not_configured"},
        )
        return {"processed": 0, "alerts": 0, "status": "disabled"}

    close_session = False
    if db_session is None:
        db_session = SessionLocal()
        close_session = True

    try:
        now = datetime.now(timezone.utc)
        since_dt = since or (now - timedelta(days=1))
        until_dt = until or now

        invoices = (
            db_session.query(BillingInvoice)
            .filter(BillingInvoice.updated_at >= since_dt)
            .filter(BillingInvoice.updated_at < until_dt)
            .all()
        )

        processed = 0
        alerts = 0
        max_drift = 0.0

        for invoice in invoices:
            processed += 1
            try:
                remote_invoice = gateway.retrieve_invoice(invoice.stripe_invoice_id)
            except stripe_error.StripeError as exc:  # pragma: no cover - Stripe failure path
                logger.exception(
                    "Failed to retrieve invoice from Stripe during reconciliation",
                    extra={
                        "event": "billing_reconcile_error",
                        "invoice_id": invoice.stripe_invoice_id,
                        "org_id": str(invoice.org_id),
                        "error": str(exc),
                    },
                )
                continue

            remote_payload = _as_dict(remote_invoice) or {}
            remote_total = _to_int(remote_payload.get("total"))
            remote_tax = _extract_tax_amount(remote_payload)

            local_total = invoice.total_minor or 0
            local_tax = invoice.tax_amount_total_minor or 0

            drift_total = _calculate_drift(local_total, remote_total)
            drift_tax = _calculate_drift(local_tax, remote_tax)
            drift_pct = max(drift_total, drift_tax)
            max_drift = max(max_drift, drift_pct)

            record_billing_reconcile_drift(str(invoice.org_id), drift_pct)

            log_extra = {
                "event": "billing_reconcile_item",
                "invoice_id": invoice.stripe_invoice_id,
                "org_id": str(invoice.org_id),
                "local_total_minor": local_total,
                "remote_total_minor": remote_total,
                "local_tax_minor": local_tax,
                "remote_tax_minor": remote_tax,
                "drift_pct": drift_pct,
            }

            if drift_pct > 1.0:
                alerts += 1
                logger.warning("Invoice drift above threshold", extra=log_extra)
            else:
                logger.info("Invoice reconciled", extra=log_extra)

        summary = {"processed": processed, "alerts": alerts, "status": "completed", "max_drift_pct": max_drift}
        logger.info(
            "Billing reconciliation finished",
            extra={"event": "billing_reconcile_batch", **summary, "since": since_dt.isoformat(), "until": until_dt.isoformat()},
        )
        return summary
    finally:
        if close_session:
            db_session.close()


__all__ = [
    "enqueue_billing_reconcile",
    "get_queue",
    "process_billing_reconciliation",
]
