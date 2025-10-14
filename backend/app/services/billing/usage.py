"""Utilities to compute and sync metered usage with Stripe."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func
from sqlalchemy.orm import Session
from stripe import error as stripe_error
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.config import settings
from app.metrics import record_billing_usage_sync
from app.models.models import (
    BillingSubscription,
    BillingUsageWindow,
    BillingUsageWindowStatusEnum,
    MessageEvent,
)
from app.services.billing.stripe_client import StripeGateway, get_stripe_gateway


logger = logging.getLogger(__name__)


@dataclass
class UsageSyncResult:
    """Aggregated counters for a usage sync batch."""

    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "processed": self.processed,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped": self.skipped,
        }


class BillingUsageService:
    """Coordinates metered usage collection and synchronization with Stripe."""

    def __init__(self, db: Session, stripe_gateway: StripeGateway | None = None) -> None:
        self.db = db
        self._stripe_gateway = stripe_gateway

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def mark_message_billable(
        self,
        *,
        message_event_id: uuid.UUID,
        occurred_at: datetime | None = None,
    ) -> None:
        """Flag a message event as billable and enqueue its window for syncing."""

        event = self.db.get(MessageEvent, message_event_id)
        if event is None:
            return

        if not event.timestamp_provider:
            event.timestamp_provider = datetime.now(timezone.utc)

        timestamp = occurred_at or event.timestamp_provider or datetime.now(timezone.utc)
        timestamp = self._ensure_tz(timestamp)

        if not event.is_billable:
            event.is_billable = True

        window = self._ensure_window(org_id=event.org_id, reference=timestamp)
        self._mark_window_pending(window, reference=timestamp)

    def ensure_backfill(self, *, now: datetime | None = None) -> None:
        """Ensure usage windows exist for the lookback horizon for all orgs."""

        current_time = self._ensure_tz(now or datetime.now(timezone.utc))
        lookback_days = max(int(settings.BILLING_USAGE_LOOKBACK_DAYS), 1)
        start_day = self._start_of_day(current_time - timedelta(days=lookback_days))
        end_day = self._start_of_day(current_time)

        subscriptions = self.db.query(BillingSubscription).all()
        for subscription in subscriptions:
            org_id = subscription.org_id
            cursor = start_day
            while cursor < end_day:
                window = self._ensure_window(org_id=org_id, reference=cursor)
                if (
                    window.next_run_at is None
                    and window.status not in {
                        BillingUsageWindowStatusEnum.processing,
                        BillingUsageWindowStatusEnum.succeeded,
                    }
                ):
                    window.next_run_at = self._next_due_at(window.period_end, current_time)
                cursor += timedelta(days=1)
        self.db.flush()

    def sync_due_windows(
        self,
        *,
        now: datetime | None = None,
        limit: int | None = None,
    ) -> UsageSyncResult:
        """Process usage windows due for synchronization."""

        current_time = self._ensure_tz(now or datetime.now(timezone.utc))
        result = UsageSyncResult()

        self.ensure_backfill(now=current_time)

        query = (
            self.db.query(BillingUsageWindow)
            .filter(BillingUsageWindow.next_run_at.isnot(None))
            .filter(BillingUsageWindow.next_run_at <= current_time)
            .filter(BillingUsageWindow.retry_count < settings.BILLING_USAGE_MAX_RETRIES)
            .order_by(BillingUsageWindow.next_run_at)
        )
        if limit:
            query = query.limit(limit)

        windows = query.all()
        if not windows:
            self.db.commit()
            return result

        gateway = self._stripe_gateway or get_stripe_gateway()

        for window in windows:
            result.processed += 1
            success = self._sync_window(window=window, now=current_time, gateway=gateway)
            if success:
                result.succeeded += 1
            else:
                result.failed += 1

        self.db.commit()
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _sync_window(
        self,
        *,
        window: BillingUsageWindow,
        now: datetime,
        gateway: StripeGateway,
    ) -> bool:
        org_id = window.org_id
        window.status = BillingUsageWindowStatusEnum.processing
        window.updated_at = now
        window.last_error = None
        self.db.flush()

        subscription = (
            self.db.query(BillingSubscription)
            .filter(BillingSubscription.org_id == org_id)
            .first()
        )
        if subscription is None or not subscription.stripe_subscription_item_id:
            self._mark_failure(
                window,
                "missing_stripe_subscription_item",
                now=now,
                terminal=False,
            )
            record_billing_usage_sync(str(org_id), "failed")
            return False

        quantity = self._calculate_quantity(
            org_id=org_id,
            period_start=window.period_start,
            period_end=window.period_end,
        )
        usage_timestamp = self._usage_timestamp(window.period_end)
        idempotency_key = self._build_idempotency_key(org_id, window.period_start, window.period_end)

        try:
            gateway.create_usage_record(
                subscription_item_id=subscription.stripe_subscription_item_id,
                quantity=quantity,
                timestamp=usage_timestamp,
                action="set",
                idempotency_key=idempotency_key,
            )
        except stripe_error.StripeError as exc:
            self._mark_failure(window, str(exc), now=now, terminal=False)
            record_billing_usage_sync(str(org_id), "failed")
            logger.warning(
                "Stripe usage record failed",
                extra={
                    "event": "billing_usage_sync_failure",
                    "org_id": str(org_id),
                    "window_id": str(window.id),
                    "error": str(exc),
                },
            )
            return False
        except Exception as exc:  # pragma: no cover - defensive guard
            self._mark_failure(window, str(exc), now=now, terminal=False)
            record_billing_usage_sync(str(org_id), "failed")
            logger.exception(
                "Unexpected error while creating Stripe usage record",
                extra={
                    "event": "billing_usage_sync_error",
                    "org_id": str(org_id),
                    "window_id": str(window.id),
                },
            )
            return False

        window.status = BillingUsageWindowStatusEnum.succeeded
        window.retry_count = 0
        window.next_run_at = None
        window.last_synced_quantity = quantity
        window.last_synced_at = now
        window.last_error = None
        self.db.flush()

        record_billing_usage_sync(str(org_id), "succeeded")
        logger.info(
            "Stripe usage record synced",
            extra={
                "event": "billing_usage_synced",
                "org_id": str(org_id),
                "window_id": str(window.id),
                "quantity": quantity,
                "period_start": window.period_start.isoformat(),
                "period_end": window.period_end.isoformat(),
            },
        )
        return True

    def _mark_failure(
        self,
        window: BillingUsageWindow,
        error: str,
        *,
        now: datetime,
        terminal: bool,
    ) -> None:
        retry_count = int(window.retry_count or 0) + 1
        window.status = BillingUsageWindowStatusEnum.failed
        window.retry_count = retry_count
        window.last_error = error[:1024]
        window.updated_at = now

        if retry_count >= settings.BILLING_USAGE_MAX_RETRIES or terminal:
            window.next_run_at = None
        else:
            backoff_seconds = min(
                settings.BILLING_USAGE_RETRY_BASE_SECONDS * (2 ** (retry_count - 1)),
                settings.BILLING_USAGE_RETRY_MAX_SECONDS,
            )
            window.next_run_at = now + timedelta(seconds=backoff_seconds)
        self.db.flush()

    def _mark_window_pending(self, window: BillingUsageWindow, *, reference: datetime) -> None:
        window.status = BillingUsageWindowStatusEnum.pending
        window.retry_count = 0
        window.last_error = None
        window.next_run_at = self._next_due_at(window.period_end, reference)
        window.updated_at = reference
        self.db.flush()

    def _ensure_window(self, *, org_id: uuid.UUID, reference: datetime) -> BillingUsageWindow:
        reference = self._ensure_tz(reference)
        period_start = self._start_of_day(reference)
        period_end = period_start + timedelta(days=1)

        window = (
            self.db.query(BillingUsageWindow)
            .filter(
                and_(
                    BillingUsageWindow.org_id == org_id,
                    BillingUsageWindow.period_start == period_start,
                    BillingUsageWindow.period_end == period_end,
                )
            )
            .first()
        )

        if window is None:
            dialect = (self.db.bind.dialect.name if self.db.bind else "postgresql").lower()
            values = {
                "id": uuid.uuid4(),
                "org_id": org_id,
                "period_start": period_start,
                "period_end": period_end,
            }

            if dialect == "postgresql":
                statement = (
                    pg_insert(BillingUsageWindow)
                    .values(**values)
                    .on_conflict_do_nothing(
                        index_elements=["org_id", "period_start", "period_end"],
                    )
                )
                self.db.execute(statement)
                self.db.flush()
            elif dialect == "sqlite":
                statement = sqlite_insert(BillingUsageWindow).values(**values)
                statement = statement.prefix_with("OR IGNORE")
                self.db.execute(statement)
                self.db.flush()

            window = (
                self.db.query(BillingUsageWindow)
                .filter(
                    and_(
                        BillingUsageWindow.org_id == org_id,
                        BillingUsageWindow.period_start == period_start,
                        BillingUsageWindow.period_end == period_end,
                    )
                )
                .first()
            )

        return window

    def _calculate_quantity(
        self,
        *,
        org_id: uuid.UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        total = (
            self.db.query(func.count(MessageEvent.id))
            .filter(MessageEvent.org_id == org_id)
            .filter(MessageEvent.direction == "outbound")
            .filter(MessageEvent.is_billable.is_(True))
            .filter(MessageEvent.timestamp_provider >= period_start)
            .filter(MessageEvent.timestamp_provider < period_end)
            .scalar()
        )
        return int(total or 0)

    @staticmethod
    def _start_of_day(moment: datetime) -> datetime:
        moment = BillingUsageService._ensure_tz(moment)
        return moment.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def _next_due_at(period_end: datetime, reference: datetime) -> datetime:
        grace = timedelta(minutes=max(int(settings.BILLING_USAGE_GRACE_MINUTES), 0))
        candidate = BillingUsageService._ensure_tz(period_end) + grace
        if candidate < reference:
            return reference
        return candidate

    @staticmethod
    def _usage_timestamp(period_end: datetime) -> int:
        boundary = BillingUsageService._ensure_tz(period_end) - timedelta(seconds=1)
        return int(boundary.timestamp())

    @staticmethod
    def _ensure_tz(moment: datetime) -> datetime:
        if moment.tzinfo is None:
            return moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(timezone.utc)

    @staticmethod
    def _build_idempotency_key(org_id: uuid.UUID, period_start: datetime, period_end: datetime) -> str:
        return f"usage:{org_id}:{BillingUsageService._ensure_tz(period_start).isoformat()}:{BillingUsageService._ensure_tz(period_end).isoformat()}"


__all__ = [
    "BillingUsageService",
    "UsageSyncResult",
]
