import sys
import uuid
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.auth import _build_token_claims, RoleEnum  # noqa: E402


def test_owner_token_includes_contacts_permissions():
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()

    claims = _build_token_claims(user_id, org_id, RoleEnum.owner)

    assert claims["sub"] == str(user_id)
    assert claims["org_id"] == str(org_id)
    assert set(claims["permissions"]) == {"contacts:read", "contacts:write"}


def test_member_token_includes_read_only_permissions():
    claims = _build_token_claims(uuid.uuid4(), uuid.uuid4(), RoleEnum.member)

    assert claims["permissions"] == ["contacts:read"]
