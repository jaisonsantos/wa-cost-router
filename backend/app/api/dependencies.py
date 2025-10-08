from __future__ import annotations

from typing import Iterable, List

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import verify_token

import uuid

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    permissions: Iterable[str] | None = payload.get("permissions")  # type: ignore[arg-type]
    if isinstance(permissions, str):
        permissions = [permissions]

    normalized_permissions: List[str]
    if permissions is None:
        normalized_permissions = []
    else:
        normalized_permissions = [str(permission) for permission in permissions]

    return {
        "user_id": uuid.UUID(payload["sub"]),
        "org_id": uuid.UUID(payload["org_id"]),
        "permissions": normalized_permissions,
    }
