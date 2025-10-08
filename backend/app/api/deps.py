"""Shared FastAPI dependencies for the public API layer."""

from __future__ import annotations

from typing import Iterable

from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict

from app.api.dependencies import get_current_user


CONTACTS_READ_PERMISSION = "contacts:read"
CONTACTS_WRITE_PERMISSION = "contacts:write"


class PaginationParams(BaseModel):
    """Typed pagination payload returned by :func:`get_pagination_params`."""

    model_config = ConfigDict(extra="forbid")

    limit: int
    offset: int


def get_pagination_params(
    *,
    limit: int = Query(50, ge=1, le=200, description="Number of records to return."),
    offset: int = Query(0, ge=0, description="Number of records to skip from the start."),
) -> PaginationParams:
    """Normalize query parameters used for paginated endpoints."""

    return PaginationParams(limit=limit, offset=offset)


def _normalize_permissions(raw_permissions: Iterable[str] | None) -> set[str]:
    if raw_permissions is None:
        return set()
    return {str(permission) for permission in raw_permissions}


def _enforce_permissions(current_user: dict, *required_permissions: str) -> dict:
    normalized = _normalize_permissions(current_user.get("permissions"))
    missing = [permission for permission in required_permissions if permission not in normalized]

    if missing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "forbidden",
                "missing_permissions": missing,
            },
        )

    return current_user


def require_contacts_read(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Ensure the authenticated subject can list/search contacts."""

    return _enforce_permissions(current_user, CONTACTS_READ_PERMISSION)


def require_contacts_write(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Ensure the authenticated subject can mutate contacts."""

    return _enforce_permissions(current_user, CONTACTS_WRITE_PERMISSION)


def require_permissions(*permissions: str):
    """Factory that creates dependencies validating arbitrary permissions."""

    def dependency(current_user: dict = Depends(get_current_user)) -> dict:
        return _enforce_permissions(current_user, *permissions)

    return dependency

