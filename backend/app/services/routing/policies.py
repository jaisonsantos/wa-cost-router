from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Callable, Iterable, List, Optional

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
    ) -> None:
        if not template_category:
            return
        if template_category.lower() != "marketing":
            return
        if not self._quiet_windows:
            return

        timestamp = self._normalize_datetime(requested_at or self._now_provider())
        current_time = timestamp.time()
        if self._is_in_quiet_window(current_time):
            raise RoutingPolicyViolation(
                code="marketing_silent_hours",
                message=(
                    "Marketing templates are blocked during quiet hours "
                    f"({self._quiet_descriptions} UTC)."
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
