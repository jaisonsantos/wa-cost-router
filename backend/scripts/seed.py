import sys
import uuid
import hashlib
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import (
    hash_password,
    encrypt_token,
    encrypt_credentials,
)  # noqa: E402
from app.models.models import (  # noqa: E402
    Organization,
    User,
    OrganizationUser,
    RoleEnum,
    WAConnection,
    RateCard,
    MessageEvent,
    Provider,
    Contact,
    ContactChannelOptIn,
    ContactSegment,
    ContactSegmentMembership,
    ContactImportJob,
    ContactStatusEnum,
    OptInStatusEnum,
    ContactImportStatusEnum,
    ProviderCredential,
)


DEFAULT_ORG_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
DEFAULT_ORG_NAME = "Demo Org"
DEFAULT_USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
DEFAULT_USER_EMAIL = "admin@demo.local"
DEFAULT_USER_PASSWORD = "demo123"
DEFAULT_PHONE_ID = "demo_phone_456"
DEFAULT_BUSINESS_ID = "demo_business_123"
DEFAULT_WEBHOOK_VERIFY_TOKEN = "my-verify-token"
DEFAULT_WEBHOOK_SECRET = "my-webhook-secret"
DEFAULT_ACCESS_TOKEN = "fake-wa-access-token"
DEFAULT_PROVIDER_NAME = "360dialog"

DEFAULT_EMAIL_PROVIDER_NAME = "SendGrid"
DEFAULT_EMAIL_WEBHOOK_TOKEN = "demo-email-webhook-token"
DEFAULT_EMAIL_WEBHOOK_SECRET = "demo-email-webhook-secret"

DEFAULT_CONTACT_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
DEFAULT_CONTACT_EMAIL = "dana.customer@example.com"
DEFAULT_CONTACT_PHONE = "+5511987654321"
DEFAULT_CONTACT_SOURCE = "seed"

DEFAULT_MARKETING_CONTACT_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")
DEFAULT_MARKETING_CONTACT_EMAIL = "john.customer@example.com"
DEFAULT_MARKETING_CONTACT_PHONE = "+5511999999999"

DEFAULT_SEGMENT_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
DEFAULT_SEGMENT_SLUG = "pilot-customers"

DEFAULT_IMPORT_JOB_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")


def seed():
    """Populate demo data without creating database structures."""
    db = SessionLocal()

    try:
        org = db.query(Organization).filter(Organization.name == DEFAULT_ORG_NAME).first()
        if not org:
            org = Organization(id=DEFAULT_ORG_ID, name=DEFAULT_ORG_NAME)
            db.add(org)
            db.flush()

        user = db.query(User).filter(User.email == DEFAULT_USER_EMAIL).first()
        if not user:
            user = User(
                id=DEFAULT_USER_ID,
                email=DEFAULT_USER_EMAIL,
                password_hash=hash_password(DEFAULT_USER_PASSWORD),
            )
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
                access_token_enc=encrypt_token(DEFAULT_ACCESS_TOKEN),
                webhook_verify_token=DEFAULT_WEBHOOK_VERIFY_TOKEN,
                webhook_secret_enc=encrypt_token(DEFAULT_WEBHOOK_SECRET),
                status="active",
            )
            db.add(connection)
            db.flush()
        else:
            connection.access_token_enc = encrypt_token(DEFAULT_ACCESS_TOKEN)
            connection.webhook_verify_token = DEFAULT_WEBHOOK_VERIFY_TOKEN
            connection.webhook_secret_enc = encrypt_token(DEFAULT_WEBHOOK_SECRET)

        now = datetime.now(timezone.utc)

        provider = (
            db.query(Provider)
            .filter(
                Provider.org_id == org.id,
                Provider.name == DEFAULT_PROVIDER_NAME,
            )
            .first()
        )
        if not provider:
            provider = Provider(
                org_id=org.id,
                name=DEFAULT_PROVIDER_NAME,
                type="whatsapp",
                status="active",
            )
            db.add(provider)
            db.flush()

        default_rates = [
            ("BR", "MARKETING", 85),
            ("BR", "UTILITY", 42),
            ("ES", "MARKETING", 95),
            ("US", "AUTHENTICATION", 120),
            ("GLOBAL", "MARKETING", 100),
        ]

        for country_iso, category, unit_cost_minor in default_rates:
            exists = (
                db.query(RateCard)
                .filter(
                    RateCard.provider_id == provider.id,
                    RateCard.country_iso == country_iso,
                    RateCard.category == category,
                )
                .first()
            )
            if not exists:
                db.add(
                    RateCard(
                        provider_id=provider.id,
                        effective_from=now,
                        source="seed",
                        country_iso=country_iso,
                        category=category,
                        unit_cost_minor=unit_cost_minor,
                        currency="USD",
                    )
                )

        email_provider = (
            db.query(Provider)
            .filter(
                Provider.org_id == org.id,
                Provider.name == DEFAULT_EMAIL_PROVIDER_NAME,
            )
            .first()
        )

        if not email_provider:
            email_provider = Provider(
                org_id=org.id,
                name=DEFAULT_EMAIL_PROVIDER_NAME,
                type="email",
                status="active",
            )
            db.add(email_provider)
            db.flush()
        else:
            email_provider.status = "active"

        email_credentials_payload = {
            "webhook_token": DEFAULT_EMAIL_WEBHOOK_TOKEN,
            "inbound_verify_token": DEFAULT_EMAIL_WEBHOOK_TOKEN,
            "inbound_signing_secret": DEFAULT_EMAIL_WEBHOOK_SECRET,
        }

        email_credentials = (
            db.query(ProviderCredential)
            .filter(
                ProviderCredential.org_id == org.id,
                ProviderCredential.provider_id == email_provider.id,
            )
            .first()
        )

        if not email_credentials:
            email_credentials = ProviderCredential(
                org_id=org.id,
                provider_id=email_provider.id,
                credentials_encrypted=encrypt_credentials(email_credentials_payload),
                is_active=True,
            )
            db.add(email_credentials)
        else:
            email_credentials.credentials_encrypted = encrypt_credentials(
                email_credentials_payload
            )
            email_credentials.is_active = True

        events_exist = db.query(MessageEvent).filter(MessageEvent.org_id == org.id).first()
        if not events_exist:
            templates = [
                ("welcome_msg", "MARKETING", "BR"),
                ("order_confirmation", "UTILITY", "BR"),
                ("promo_campaign", "MARKETING", "ES"),
                ("password_reset", "AUTHENTICATION", "US"),
            ]

            cc_map = {"BR": "+55", "ES": "+34", "US": "+1"}

            for index in range(20):
                template_name, category, country_iso = templates[index % len(templates)]

                rate = (
                    db.query(RateCard)
                    .filter(
                        RateCard.provider_id == provider.id,
                        RateCard.country_iso == country_iso,
                        RateCard.category == category,
                    )
                    .order_by(RateCard.effective_from.desc())
                    .first()
                )

                if not rate and country_iso != "GLOBAL":
                    rate = (
                        db.query(RateCard)
                        .filter(
                            RateCard.provider_id == provider.id,
                            RateCard.country_iso == "GLOBAL",
                            RateCard.category == category,
                        )
                        .order_by(RateCard.effective_from.desc())
                        .first()
                    )

                unit_cost_minor = rate.unit_cost_minor if rate else 0
                currency = rate.currency if rate else "USD"

                multiplier = 1.35 if category == "MARKETING" else 1.2
                baseline_cost_minor = int(unit_cost_minor * multiplier) if unit_cost_minor else 0
                if baseline_cost_minor < unit_cost_minor:
                    baseline_cost_minor = unit_cost_minor

                db.add(
                    MessageEvent(
                        org_id=org.id,
                        connection_id=connection.id,
                        provider_event_id=f"evt_{index:02d}_sandbox",
                        direction="outbound",
                        template_name=template_name,
                        category=category,
                        country_iso=country_iso,
                        phone_cc=cc_map.get(country_iso),
                        timestamp_provider=now - timedelta(days=index % 7),
                        delivery_status="delivered",
                        unit_cost_minor=unit_cost_minor,
                        baseline_cost_minor=baseline_cost_minor,
                        currency=currency,
                    )
                )

        demo_contact = (
            db.query(Contact)
            .filter(Contact.org_id == org.id, Contact.email == DEFAULT_CONTACT_EMAIL)
            .first()
        )
        seed_timestamp = datetime(2024, 1, 15, tzinfo=timezone.utc)
        if not demo_contact:
            demo_contact = Contact(
                id=DEFAULT_CONTACT_ID,
                org_id=org.id,
                full_name="Dona Dana",
                first_name="Dona",
                last_name="Dana",
                email=DEFAULT_CONTACT_EMAIL,
                phone=DEFAULT_CONTACT_PHONE,
                status=ContactStatusEnum.active,
                source=DEFAULT_CONTACT_SOURCE,
                source_metadata={"seed": True},
                proof_hash=hashlib.sha256(b"contact:dona-dana:seed:v1").hexdigest(),
                created_at=seed_timestamp,
                updated_at=seed_timestamp,
            )
            db.add(demo_contact)
            db.flush()

        marketing_contact = (
            db.query(Contact)
            .filter(Contact.org_id == org.id)
            .filter(Contact.phone == DEFAULT_MARKETING_CONTACT_PHONE)
            .first()
        )
        if not marketing_contact:
            marketing_contact = Contact(
                id=DEFAULT_MARKETING_CONTACT_ID,
                org_id=org.id,
                full_name="John Customer",
                first_name="John",
                last_name="Customer",
                email=DEFAULT_MARKETING_CONTACT_EMAIL,
                phone=DEFAULT_MARKETING_CONTACT_PHONE,
                status=ContactStatusEnum.active,
                source=DEFAULT_CONTACT_SOURCE,
                source_metadata={"seed": True},
                proof_hash=hashlib.sha256(b"contact:john-customer:seed:v1").hexdigest(),
                created_at=seed_timestamp,
                updated_at=seed_timestamp,
            )
            db.add(marketing_contact)
            db.flush()

        opt_in = (
            db.query(ContactChannelOptIn)
            .filter(
                ContactChannelOptIn.contact_id == demo_contact.id,
                ContactChannelOptIn.channel == "whatsapp",
                ContactChannelOptIn.channel_address == DEFAULT_CONTACT_PHONE,
                ContactChannelOptIn.version == 1,
            )
            .first()
        )
        if not opt_in:
            opt_in = ContactChannelOptIn(
                org_id=org.id,
                contact_id=demo_contact.id,
                channel="whatsapp",
                channel_address=DEFAULT_CONTACT_PHONE,
                status=OptInStatusEnum.granted,
                version=1,
                legal_basis="legitimate_interest",
                captured_at=seed_timestamp,
                source=DEFAULT_CONTACT_SOURCE,
                source_metadata={"seed": True},
                evidence_uri="https://example.com/proof/whatsapp-opt-in",
                proof_hash=hashlib.sha256(b"optin:whatsapp:dona-dana:v1").hexdigest(),
                created_at=seed_timestamp,
                updated_at=seed_timestamp,
            )
            db.add(opt_in)

        marketing_opt_in = (
            db.query(ContactChannelOptIn)
            .filter(ContactChannelOptIn.contact_id == marketing_contact.id)
            .filter(ContactChannelOptIn.channel == "whatsapp")
            .filter(ContactChannelOptIn.channel_address == DEFAULT_MARKETING_CONTACT_PHONE)
            .filter(ContactChannelOptIn.version == 1)
            .first()
        )
        if not marketing_opt_in:
            marketing_opt_in = ContactChannelOptIn(
                org_id=org.id,
                contact_id=marketing_contact.id,
                channel="whatsapp",
                channel_address=DEFAULT_MARKETING_CONTACT_PHONE,
                status=OptInStatusEnum.granted,
                version=1,
                legal_basis="opt_in",
                captured_at=seed_timestamp,
                source=DEFAULT_CONTACT_SOURCE,
                source_metadata={"seed": True},
                evidence_uri="https://example.com/proof/whatsapp-opt-in-john",
                proof_hash=hashlib.sha256(b"optin:whatsapp:john-customer:v1").hexdigest(),
                created_at=seed_timestamp,
                updated_at=seed_timestamp,
            )
            db.add(marketing_opt_in)

        pilot_segment = (
            db.query(ContactSegment)
            .filter(ContactSegment.org_id == org.id, ContactSegment.slug == DEFAULT_SEGMENT_SLUG)
            .first()
        )
        if not pilot_segment:
            pilot_segment = ContactSegment(
                id=DEFAULT_SEGMENT_ID,
                org_id=org.id,
                slug=DEFAULT_SEGMENT_SLUG,
                name="Clientes Piloto",
                description="Contatos habilitados para o piloto multi-tenant.",
                criteria={"type": "static", "seed": True},
                source=DEFAULT_CONTACT_SOURCE,
                source_metadata={"seed": True},
                proof_hash=hashlib.sha256(b"segment:pilot-customers:v1").hexdigest(),
                created_at=seed_timestamp,
                updated_at=seed_timestamp,
            )
            db.add(pilot_segment)
            db.flush()

        membership = (
            db.query(ContactSegmentMembership)
            .filter(
                ContactSegmentMembership.contact_id == demo_contact.id,
                ContactSegmentMembership.segment_id == pilot_segment.id,
            )
            .first()
        )
        if not membership:
            membership = ContactSegmentMembership(
                org_id=org.id,
                contact_id=demo_contact.id,
                segment_id=pilot_segment.id,
                membership_origin="seed",
                valid_from=seed_timestamp,
                source=DEFAULT_CONTACT_SOURCE,
                source_metadata={"seed": True},
                proof_hash=hashlib.sha256(b"segment-membership:dona-dana:pilot").hexdigest(),
                created_at=seed_timestamp,
                updated_at=seed_timestamp,
            )
            db.add(membership)

        marketing_membership = (
            db.query(ContactSegmentMembership)
            .filter(ContactSegmentMembership.contact_id == marketing_contact.id)
            .filter(ContactSegmentMembership.segment_id == pilot_segment.id)
            .first()
        )
        if not marketing_membership:
            marketing_membership = ContactSegmentMembership(
                org_id=org.id,
                contact_id=marketing_contact.id,
                segment_id=pilot_segment.id,
                membership_origin="seed",
                valid_from=seed_timestamp,
                source=DEFAULT_CONTACT_SOURCE,
                source_metadata={"seed": True},
                proof_hash=hashlib.sha256(b"segment-membership:john-customer:pilot").hexdigest(),
                created_at=seed_timestamp,
                updated_at=seed_timestamp,
            )
            db.add(marketing_membership)

        import_job = (
            db.query(ContactImportJob)
            .filter(ContactImportJob.id == DEFAULT_IMPORT_JOB_ID)
            .first()
        )
        if not import_job:
            import_job = ContactImportJob(
                id=DEFAULT_IMPORT_JOB_ID,
                org_id=org.id,
                requested_by=DEFAULT_USER_EMAIL,
                input_uri="s3://demo-imports/contacts.csv",
                status=ContactImportStatusEnum.completed,
                total_rows=1,
                processed_rows=1,
                error_rows=0,
                started_at=seed_timestamp,
                completed_at=seed_timestamp + timedelta(minutes=5),
                source=DEFAULT_CONTACT_SOURCE,
                source_metadata={"seed": True},
                proof_hash=hashlib.sha256(b"import:contacts:demo:v1").hexdigest(),
                created_at=seed_timestamp,
                updated_at=seed_timestamp + timedelta(minutes=5),
            )
            db.add(import_job)

        db.commit()
        print("✅ Seed data created successfully (idempotent).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
