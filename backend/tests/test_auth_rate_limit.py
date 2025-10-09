import sys
from pathlib import Path

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.core.rate_limiter import RateLimiter, get_rate_limiter  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import Organization, OrganizationUser, RoleEnum, User  # noqa: E402


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
def client(db_session, monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    limiter = RateLimiter(fake, key_prefix="login-test")

    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_rate_limiter] = lambda: limiter

    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_PER_MIN", 2)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_rate_limiter, None)


def _create_user(db_session, email: str, password: str, org_name: str):
    org = Organization(name=org_name)
    db_session.add(org)
    db_session.flush()

    user = User(email=email, password_hash=hash_password(password))
    db_session.add(user)
    db_session.flush()

    membership = OrganizationUser(org_id=org.id, user_id=user.id, role=RoleEnum.owner)
    db_session.add(membership)
    db_session.commit()

    return user, membership


def test_login_rate_limit_exceeded_and_isolated(client, db_session):
    test_client = client

    user_a, _ = _create_user(db_session, "owner-a@example.com", "secret", "Org A")
    user_b, _ = _create_user(db_session, "owner-b@example.com", "secret", "Org B")

    payload_a = {"email": user_a.email, "password": "secret"}

    response1 = test_client.post("/auth/login", json=payload_a)
    assert response1.status_code == 200

    response2 = test_client.post("/auth/login", json=payload_a)
    assert response2.status_code == 200

    response3 = test_client.post("/auth/login", json=payload_a)
    assert response3.status_code == 429
    assert response3.headers["Retry-After"].isdigit()
    assert response3.headers["X-RateLimit-Remaining"] == "0"

    # Another organization remains unaffected
    response_other = test_client.post(
        "/auth/login",
        json={"email": user_b.email, "password": "secret"},
    )
    assert response_other.status_code == 200
