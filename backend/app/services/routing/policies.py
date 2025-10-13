from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional

from app.core.config import settings


logger = logging.getLogger(__name__)


class RoutingPolicyViolation(Exception):
    """Erro lançado quando alguma política de envio é violada."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class QuietWindow:
    start: time
    end: time

    def contains(self, current: time) -> bool:
        if self.start <= self.end:
            return self.start <= current < self.end
        # janela atravessa meia-noite
        return current >= self.start or current < self.end

    def description(self) -> str:
        return f"{self.start.strftime('%H:%M')}-{self.end.strftime('%H:%M')}"


class RoutingPolicyService:
    """Serviço responsável por validar políticas de roteamento antes do envio."""

    def __init__(
        self,
        *,
        quiet_hours: Optional[Iterable[str]] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
    ) -> None:
        raw_windows = list(quiet_hours) if quiet_hours is not None else settings.MARKETING_SILENT_HOURS_UTC
        self._quiet_windows: List[QuietWindow] = self._parse_quiet_windows(raw_windows)
        self._quiet_descriptions = ", ".join(window.description() for window in self._quiet_windows)
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def validate(
        self,
        *,
        template_category: Optional[str],
        channel: Optional[str],
        requested_at: Optional[datetime] = None,
        template_metadata: Optional[Dict[str, Any]] = None,
        country_iso: Optional[str] = None,
    ) -> None:
        timestamp = self._normalize_datetime(requested_at or self._now_provider())
        current_time = timestamp.time()

        self._validate_template_metadata(
            template_metadata or {},
            country_iso=country_iso,
            current_time=current_time,
        )

        if not template_category:
            return
        if template_category.lower() != "marketing":
            return
        if not self._quiet_windows:
            return

        if self._is_in_quiet_window(current_time):
            raise RoutingPolicyViolation(
                code="marketing_silent_hours",
                message=(
                    "Marketing templates are blocked during quiet hours "
                    f"({self._quiet_descriptions} UTC)."
                ),
            )

    def _validate_template_metadata(
        self,
        metadata: Dict[str, Any],
        *,
        country_iso: Optional[str],
        current_time: time,
    ) -> None:
        if not metadata:
            return

        normalized_country = country_iso.upper() if country_iso else None
        country_display = normalized_country or "unknown"

        blocked_countries = self._normalize_country_list(metadata.get("blocked_countries"))
        if blocked_countries and normalized_country in blocked_countries:
            raise RoutingPolicyViolation(
                code="template_blocked_country",
                message=(
                    "Template cannot be sent to the requested country due to "
                    f"provider restrictions ({country_display})."
                ),
            )

        allowed_countries = self._normalize_country_list(metadata.get("allowed_countries"))
        if allowed_countries and normalized_country not in allowed_countries:
            raise RoutingPolicyViolation(
                code="template_country_not_allowed",
                message=(
                    "Template is restricted to specific countries "
                    f"({', '.join(allowed_countries)})."
                ),
            )

        allowed_windows = self._parse_quiet_windows(metadata.get("allowed_hours") or [])
        if allowed_windows and not any(window.contains(current_time) for window in allowed_windows):
            allowed_desc = ", ".join(window.description() for window in allowed_windows)
            raise RoutingPolicyViolation(
                code="template_outside_allowed_hours",
                message=(
                    "Template can only be sent during allowed hours "
                    f"({allowed_desc} UTC)."
                ),
            )

        blocked_windows = self._parse_quiet_windows(metadata.get("blocked_hours") or [])
        if blocked_windows and any(window.contains(current_time) for window in blocked_windows):
            blocked_desc = ", ".join(window.description() for window in blocked_windows)
            raise RoutingPolicyViolation(
                code="template_blocked_hours",
                message=(
                    "Template cannot be sent during blocked hours "
                    f"({blocked_desc} UTC)."
                ),
            )

    def _is_in_quiet_window(self, current: time) -> bool:
        return any(window.contains(current) for window in self._quiet_windows)

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _parse_quiet_windows(values: Iterable[str]) -> List[QuietWindow]:
        windows: List[QuietWindow] = []
        for raw_value in values:
            if not raw_value:
                continue
            try:
                start_raw, end_raw = raw_value.split("-", 1)
                start_time = datetime.strptime(start_raw.strip(), "%H:%M").time()
                end_time = datetime.strptime(end_raw.strip(), "%H:%M").time()
            except (ValueError, AttributeError):
                logger.warning("Ignoring invalid quiet hour window %r", raw_value)
                continue
            windows.append(QuietWindow(start=start_time, end=end_time))
        return windows

    @staticmethod
    def _normalize_country_list(values: Any) -> List[str]:
        if not isinstance(values, Iterable) or isinstance(values, (str, bytes)):
            return []
        normalized: List[str] = []
        for value in values:
            if not isinstance(value, str):
                continue
            candidate = value.strip().upper()
            if len(candidate) in {2, 3} and candidate.isalpha():
                normalized.append(candidate)
        return normalized
