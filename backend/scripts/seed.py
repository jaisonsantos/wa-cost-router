import sys
from datetime import datetime, timedelta
import random

sys.path.insert(0, "/app")

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password, encrypt_token  # noqa: E402
from app.models.models import (  # noqa: E402
    Organization,
    User,
    OrganizationUser,
    RoleEnum,
    WAConnection,
    RateCard,
    MessageEvent,
)


DEFAULT_ORG_NAME = "Demo Org"
DEFAULT_USER_EMAIL = "admin@demo.local"
DEFAULT_USER_PASSWORD = "demo123"
DEFAULT_PHONE_ID = "demo_phone_456"
DEFAULT_BUSINESS_ID = "demo_business_123"


def seed():
    """Populate demo data without creating database structures."""
    db = SessionLocal()

    try:
        org = db.query(Organization).filter(Organization.name == DEFAULT_ORG_NAME).first()
        if not org:
            org = Organization(name=DEFAULT_ORG_NAME)
            db.add(org)
            db.flush()

        user = db.query(User).filter(User.email == DEFAULT_USER_EMAIL).first()
        if not user:
            user = User(email=DEFAULT_USER_EMAIL, password_hash=hash_password(DEFAULT_USER_PASSWORD))
            db.add(user)
            db.flush()

        membership = (
            db.query(OrganizationUser)
            .filter(
                OrganizationUser.org_id == org.id,
                OrganizationUser.user_id == user.id,
            )
            .first()
        )
        if not membership:
            db.add(
                OrganizationUser(
                    org_id=org.id,
                    user_id=user.id,
                    role=RoleEnum.owner,
                )
            )

        connection = (
            db.query(WAConnection)
            .filter(
                WAConnection.org_id == org.id,
                WAConnection.phone_id == DEFAULT_PHONE_ID,
            )
            .first()
        )
        if not connection:
            connection = WAConnection(
                org_id=org.id,
                business_id=DEFAULT_BUSINESS_ID,
                phone_id=DEFAULT_PHONE_ID,
                access_token_enc=encrypt_token("fake_token_abc"),
                status="active",
            )
            db.add(connection)
            db.flush()

        now = datetime.utcnow()
        default_rates = [
            ("BR", "MARKETING", 85),
            ("BR", "UTILITY", 42),
            ("ES", "MARKETING", 95),
            ("GLOBAL", "MARKETING", 100),
        ]

        for country_iso, category, unit_cost_minor in default_rates:
            exists = (
                db.query(RateCard)
                .filter(
                    RateCard.country_iso == country_iso,
                    RateCard.category == category,
                    RateCard.source == "seed",
                )
                .first()
            )
            if not exists:
                db.add(
                    RateCard(
                        effective_from=now,
                        source="seed",
                        country_iso=country_iso,
                        category=category,
                        unit_cost_minor=unit_cost_minor,
                        currency="USD",
                    )
                )

        events_exist = db.query(MessageEvent).filter(MessageEvent.org_id == org.id).first()
        if not events_exist:
            countries = ["BR", "ES", "US", "MX"]
            categories = ["MARKETING", "UTILITY", "AUTHENTICATION"]
            templates = ["welcome_msg", "order_confirmation", "promo_campaign"]

            for i in range(20):
                db.add(
                    MessageEvent(
                        org_id=org.id,
                        connection_id=connection.id,
                        provider_event_id=f"evt_{i}_{random.randint(1000, 9999)}",
                        direction="outbound",
                        template_name=random.choice(templates),
                        category=random.choice(categories),
                        country_iso=random.choice(countries),
                        phone_cc="+55",
                        timestamp_provider=now - timedelta(days=random.randint(0, 7)),
                        delivery_status="delivered",
                    )
                )

        db.commit()
        print("✅ Seed data created successfully (idempotent).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
