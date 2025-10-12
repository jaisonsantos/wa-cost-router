import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@compiles(PGUUID, "sqlite")
def compile_uuid_sqlite(element, compiler, **kwargs):  # pragma: no cover - SQLAlchemy hook
    return "CHAR(36)"


from app.api.dependencies import get_current_user  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.core.security import encrypt_credentials  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import (  # noqa: E402
    Organization,
    Provider,
    ProviderCredential,
    WATemplate,
)


TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture(scope="session", autouse=True)
def create_database():
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def db_session(create_database):
    connection = TEST_ENGINE.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    org_id = uuid.uuid4()
    organization = Organization(id=org_id, name="Templates Org")
    db_session.add(organization)
    db_session.commit()

    def override_current_user():
        return {
            "user_id": uuid.uuid4(),
            "org_id": org_id,
            "permissions": ["templates:read", "templates:write"],
        }

    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as test_client:
        yield test_client, org_id

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def _create_template(
    session,
    *,
    org_id: uuid.UUID,
    name: str,
    language: str,
    status: str = "pending",
    category: str = "marketing",
    meta: Dict[str, Any] | None = None,
) -> WATemplate:
    template = WATemplate(
        org_id=org_id,
        name=name,
        language=language,
        status=status,
        category=category,
        meta=meta or {},
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


def _seed_provider(
    session,
    *,
    org_id: uuid.UUID,
    name: str = "Sandbox WA",
    provider_type: str = "whatsapp",
    credentials: Dict[str, Any] | None = None,
) -> Provider:
    provider = Provider(
        org_id=org_id,
        name=name,
        type=provider_type,
        status="active",
        meta={"sandbox": {"latency_ms": 10}},
    )
    session.add(provider)
    session.flush()

    credential_payload = credentials or {"access_token": "sandbox-token"}
    credential = ProviderCredential(
        org_id=org_id,
        provider_id=provider.id,
        credentials_encrypted=encrypt_credentials(credential_payload),
        is_active=True,
    )
    session.add(credential)
    session.commit()
    return provider


def test_template_crud_and_filters(client):
    test_client, org_id = client

    payloads = [
        {
            "name": "welcome_flow",
            "category": "marketing",
            "language": "en_US",
            "status": "approved",
            "meta": {"components": 1},
        },
        {
            "name": "reengage",
            "category": "utility",
            "language": "pt_BR",
            "status": "pending",
            "meta": {"components": 2},
        },
    ]

    for payload in payloads:
        response = test_client.post("/templates/", json=payload)
        assert response.status_code == 201

    list_response = test_client.get("/templates/")
    assert list_response.status_code == 200
    templates = list_response.json()
    assert len(templates) == 2

    language_response = test_client.get("/templates/", params={"language": "pt_BR"})
    assert language_response.status_code == 200
    assert len(language_response.json()) == 1
    assert language_response.json()[0]["name"] == "reengage"

    status_response = test_client.get("/templates/", params={"status": "approved"})
    assert status_response.status_code == 200
    assert len(status_response.json()) == 1
    assert status_response.json()[0]["name"] == "welcome_flow"

    created_template_id = status_response.json()[0]["id"]
    patch_response = test_client.patch(
        f"/templates/{created_template_id}",
        json={"status": "inactive", "meta": {"components": 3}},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "inactive"
    assert patch_response.json()["meta"] == {"components": 3}

    delete_response = test_client.delete(f"/templates/{created_template_id}")
    assert delete_response.status_code == 204

    final_list = test_client.get("/templates/")
    assert final_list.status_code == 200
    final_templates = final_list.json()
    assert len(final_templates) == 1
    assert final_templates[0]["name"] == "reengage"


def test_template_sync_collects_languages_and_statuses(client, db_session, monkeypatch):
    test_client, org_id = client

    existing = _create_template(
        db_session,
        org_id=org_id,
        name="welcome_flow",
        language="en_US",
        status="pending",
    )

    provider = _seed_provider(
        db_session,
        org_id=org_id,
        credentials={
            "access_token": "sandbox-token",
            "templates": [
                {
                    "name": "welcome_flow",
                    "language": "en_US",
                    "status": "approved",
                    "category": "marketing",
                    "meta": {"components": 2},
                },
                {
                    "name": "winter_campaign",
                    "language": "es_ES",
                    "status": "rejected",
                    "category": "marketing",
                    "meta": {"components": 1},
                },
            ],
        },
    )

    class _StubConnector:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def list_templates(self) -> List[Dict[str, Any]]:
            return [
                {
                    "name": "welcome_flow",
                    "language": "en_US",
                    "status": "approved",
                    "category": "marketing",
                    "meta": {"components": 2},
                },
                {
                    "name": "winter_campaign",
                    "language": "es_ES",
                    "status": "rejected",
                    "category": "marketing",
                    "meta": {"components": 1},
                },
            ]

        async def health_check(self) -> Dict[str, Any]:  # pragma: no cover - not used
            return {"healthy": True}

    def _connector_factory(*args, **kwargs):
        return _StubConnector()

    monkeypatch.setattr("app.api.templates.get_connector", _connector_factory)

    response = test_client.post("/templates/sync")
    assert response.status_code == 200
    payload = response.json()
    assert payload["synced"] == 2
    assert sorted(payload["languages"]) == ["en_US", "es_ES"]
    assert sorted(payload["statuses"]) == ["approved", "rejected"]
    assert payload["providers"][0]["provider"] == provider.name

    db_session.refresh(existing)
    assert existing.status == "approved"
    assert existing.meta == {"components": 2}

    stored_new = (
        db_session.query(WATemplate)
        .filter(WATemplate.org_id == org_id, WATemplate.name == "winter_campaign")
        .one()
    )
    assert stored_new.language == "es_ES"
    assert stored_new.status == "rejected"
