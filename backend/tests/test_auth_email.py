import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.auth import RegisterRequest


def test_register_request_allows_demo_local_email():
    request = RegisterRequest(
        email="Postman+123@Demo.LOCAL",
        password="secret",
        org_name="Org",
    )

    assert request.email == "Postman+123@demo.local"


def test_register_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        RegisterRequest(email="not-an-email", password="secret", org_name="Org")
