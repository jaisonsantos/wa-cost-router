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
    MessageJob,
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
    Conversation,
    QueueEntry,
    SlaSnapshot,
    ConversationStatusEnum,
    QueueStatusEnum,
    JobStatusEnum,
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

DEFAULT_EMAIL_PROVIDER_NAME = "SendGrid Sandbox"
DEFAULT_EMAIL_WEBHOOK_TOKEN = "demo-email-webhook-token"
DEFAULT_EMAIL_WEBHOOK_SECRET = "demo-email-webhook-secret"
DEFAULT_EMAIL_API_KEY = "SG.fake-sandbox-key"
DEFAULT_EMAIL_FROM_ADDRESS = "noreply@demo.local"
DEFAULT_EMAIL_UNIT_COST_MINOR = 75

DEFAULT_SMS_PROVIDER_NAME = "Twilio Sandbox"
DEFAULT_SMS_ACCOUNT_SID = "AC00000000000000000000000000000000"
DEFAULT_SMS_AUTH_TOKEN = "demo-sms-auth-token"
DEFAULT_SMS_FROM_NUMBER = "+15558675309"
DEFAULT_SMS_WEBHOOK_TOKEN = "demo-sms-webhook-token"
DEFAULT_SMS_UNIT_COST_MINOR = 140

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

        email_provider_meta = {
            "channels": {
                "email": {
                    "from_address": DEFAULT_EMAIL_FROM_ADDRESS,
                    "sandbox": True,
                }
            },
            "provider": "sendgrid",
            "required_fields": [
                "api_key",
                "from_email",
                "inbound_signing_secret",
                "webhook_token",
            ],
            "defaults": {
                "from_email": DEFAULT_EMAIL_FROM_ADDRESS,
                "webhook_token": DEFAULT_EMAIL_WEBHOOK_TOKEN,
            },
            "compliance": {
                "dns": ["Configure SPF e DKIM antes de enviar e-mails reais."],
                "consent": ["Respeite cancelamentos (unsubscribe) em até 24 horas."],
            },
        }

        if not email_provider:
            email_provider = Provider(
                org_id=org.id,
                name=DEFAULT_EMAIL_PROVIDER_NAME,
                type="email",
                status="active",
                meta=email_provider_meta,
            )
            db.add(email_provider)
            db.flush()
        else:
            email_provider.status = "active"
            email_provider.meta = email_provider_meta

        email_credentials_payload = {
            "api_key": DEFAULT_EMAIL_API_KEY,
            "from_email": DEFAULT_EMAIL_FROM_ADDRESS,
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

        email_rate = (
            db.query(RateCard)
            .filter(
                RateCard.provider_id == email_provider.id,
                RateCard.country_iso == "GLOBAL",
                RateCard.category == "MARKETING",
            )
            .order_by(RateCard.effective_from.desc())
            .first()
        )

        if not email_rate:
            db.add(
                RateCard(
                    provider_id=email_provider.id,
                    effective_from=now,
                    source="seed",
                    country_iso="GLOBAL",
                    category="MARKETING",
                    unit_cost_minor=DEFAULT_EMAIL_UNIT_COST_MINOR,
                    currency="USD",
                )
            )

        sms_provider = (
            db.query(Provider)
            .filter(
                Provider.org_id == org.id,
                Provider.name == DEFAULT_SMS_PROVIDER_NAME,
            )
            .first()
        )

        sms_provider_meta = {
            "channels": {
                "sms": {
                    "inbound_numbers": [DEFAULT_SMS_FROM_NUMBER],
                    "sandbox": True,
                }
            },
            "provider": "twilio",
            "required_fields": [
                "account_sid",
                "auth_token",
                "from_number",
            ],
            "defaults": {
                "from_number": DEFAULT_SMS_FROM_NUMBER,
                "account_sid": DEFAULT_SMS_ACCOUNT_SID,
            },
            "compliance": {
                "registrations": [
                    "Para produção, registre campanhas 10DLC associadas a este remetente.",
                ],
            },
        }

        if not sms_provider:
            sms_provider = Provider(
                org_id=org.id,
                name=DEFAULT_SMS_PROVIDER_NAME,
                type="sms",
                status="active",
                meta=sms_provider_meta,
            )
            db.add(sms_provider)
            db.flush()
        else:
            sms_provider.status = "active"
            sms_provider.meta = sms_provider_meta

        sms_credentials_payload = {
            "account_sid": DEFAULT_SMS_ACCOUNT_SID,
            "auth_token": DEFAULT_SMS_AUTH_TOKEN,
            "from_number": DEFAULT_SMS_FROM_NUMBER,
            "inbound_verify_token": DEFAULT_SMS_WEBHOOK_TOKEN,
        }

        sms_credentials = (
            db.query(ProviderCredential)
            .filter(
                ProviderCredential.org_id == org.id,
                ProviderCredential.provider_id == sms_provider.id,
            )
            .first()
        )

        if not sms_credentials:
            sms_credentials = ProviderCredential(
                org_id=org.id,
                provider_id=sms_provider.id,
                credentials_encrypted=encrypt_credentials(sms_credentials_payload),
                is_active=True,
            )
            db.add(sms_credentials)
        else:
            sms_credentials.credentials_encrypted = encrypt_credentials(
                sms_credentials_payload
            )
            sms_credentials.is_active = True

        sms_rate = (
            db.query(RateCard)
            .filter(
                RateCard.provider_id == sms_provider.id,
                RateCard.country_iso == "BR",
                RateCard.category == "MARKETING",
            )
            .order_by(RateCard.effective_from.desc())
            .first()
        )

        if not sms_rate:
            db.add(
                RateCard(
                    provider_id=sms_provider.id,
                    effective_from=now,
                    source="seed",
                    country_iso="BR",
                    category="MARKETING",
                    unit_cost_minor=DEFAULT_SMS_UNIT_COST_MINOR,
                    currency="USD",
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

        email_opt_in = (
            db.query(ContactChannelOptIn)
            .filter(ContactChannelOptIn.contact_id == demo_contact.id)
            .filter(ContactChannelOptIn.channel == "email")
            .filter(ContactChannelOptIn.channel_address == DEFAULT_CONTACT_EMAIL)
            .filter(ContactChannelOptIn.version == 1)
            .first()
        )
        if not email_opt_in:
            email_opt_in = ContactChannelOptIn(
                org_id=org.id,
                contact_id=demo_contact.id,
                channel="email",
                channel_address=DEFAULT_CONTACT_EMAIL,
                status=OptInStatusEnum.granted,
                version=1,
                legal_basis="opt_in",
                captured_at=seed_timestamp,
                source=DEFAULT_CONTACT_SOURCE,
                source_metadata={"seed": True},
                evidence_uri="https://example.com/proof/email-opt-in",
                proof_hash=hashlib.sha256(b"optin:email:dona-dana:v1").hexdigest(),
                created_at=seed_timestamp,
                updated_at=seed_timestamp,
            )
            db.add(email_opt_in)

        sms_opt_in = (
            db.query(ContactChannelOptIn)
            .filter(ContactChannelOptIn.contact_id == marketing_contact.id)
            .filter(ContactChannelOptIn.channel == "sms")
            .filter(ContactChannelOptIn.channel_address == DEFAULT_MARKETING_CONTACT_PHONE)
            .filter(ContactChannelOptIn.version == 1)
            .first()
        )
        if not sms_opt_in:
            sms_opt_in = ContactChannelOptIn(
                org_id=org.id,
                contact_id=marketing_contact.id,
                channel="sms",
                channel_address=DEFAULT_MARKETING_CONTACT_PHONE,
                status=OptInStatusEnum.granted,
                version=1,
                legal_basis="opt_in",
                captured_at=seed_timestamp,
                source=DEFAULT_CONTACT_SOURCE,
                source_metadata={"seed": True},
                evidence_uri="https://example.com/proof/sms-opt-in-john",
                proof_hash=hashlib.sha256(b"optin:sms:john-customer:v1").hexdigest(),
                created_at=seed_timestamp,
                updated_at=seed_timestamp,
            )
            db.add(sms_opt_in)

        jobs_by_channel = {}
        job_definitions = [
            {
                "idempotency_key": "seed:whatsapp:welcome",
                "to_number": DEFAULT_CONTACT_PHONE,
                "channel": "whatsapp",
                "channel_address": DEFAULT_CONTACT_PHONE,
                "contact_id": demo_contact.id,
                "template_id": "welcome_msg",
                "template_category": "MARKETING",
                "variables": {"body_params": ["Dona"]},
                "country_iso": "BR",
                "status": JobStatusEnum.delivered,
            },
            {
                "idempotency_key": "seed:email:onboarding",
                "to_number": DEFAULT_CONTACT_EMAIL,
                "channel": "email",
                "channel_address": DEFAULT_CONTACT_EMAIL,
                "contact_id": demo_contact.id,
                "template_id": "welcome_email",
                "template_category": "MARKETING",
                "variables": {
                    "subject": "Bem-vinda ao piloto",
                    "body_params": ["Dona"],
                },
                "country_iso": "GLOBAL",
                "status": JobStatusEnum.delivered,
            },
            {
                "idempotency_key": "seed:sms:promo",
                "to_number": DEFAULT_MARKETING_CONTACT_PHONE,
                "channel": "sms",
                "channel_address": DEFAULT_MARKETING_CONTACT_PHONE,
                "contact_id": marketing_contact.id,
                "template_id": "promo_sms",
                "template_category": "MARKETING",
                "variables": {"body_params": ["Oferta especial"]},
                "country_iso": "BR",
                "status": JobStatusEnum.delivered,
            },
        ]

        for job_def in job_definitions:
            job = (
                db.query(MessageJob)
                .filter(
                    MessageJob.org_id == org.id,
                    MessageJob.idempotency_key == job_def["idempotency_key"],
                )
                .first()
            )

            if not job:
                job = MessageJob(
                    org_id=org.id,
                    idempotency_key=job_def["idempotency_key"],
                    to_number=job_def["to_number"],
                    channel=job_def["channel"],
                    channel_address=job_def["channel_address"],
                    contact_id=job_def.get("contact_id"),
                    template_id=job_def["template_id"],
                    template_category=job_def.get("template_category"),
                    variables=job_def.get("variables"),
                    country_iso=job_def.get("country_iso"),
                    status=job_def.get("status", JobStatusEnum.delivered),
                    created_at=seed_timestamp,
                )
                db.add(job)
                db.flush()
            else:
                job.to_number = job_def["to_number"]
                job.channel = job_def["channel"]
                job.channel_address = job_def["channel_address"]
                job.contact_id = job_def.get("contact_id")
                job.template_category = job_def.get("template_category")
                job.country_iso = job_def.get("country_iso")
                job.variables = job_def.get("variables")
                job.status = job_def.get("status", JobStatusEnum.delivered)

            jobs_by_channel[job_def["channel"]] = job

        whatsapp_job = jobs_by_channel.get("whatsapp")
        email_job = jobs_by_channel.get("email")
        sms_job = jobs_by_channel.get("sms")

        templates = [
            ("welcome_msg", "MARKETING", "BR"),
            ("order_confirmation", "UTILITY", "BR"),
            ("promo_campaign", "MARKETING", "ES"),
            ("password_reset", "AUTHENTICATION", "US"),
        ]

        cc_map = {"BR": "+55", "ES": "+34", "US": "+1", "GLOBAL": "+1"}
        contact_cycle = [demo_contact.id, marketing_contact.id]

        for index in range(20):
            template_name, category, country_iso = templates[index % len(templates)]
            provider_event_id = f"evt_{index:02d}_sandbox"

            exists = (
                db.query(MessageEvent)
                .filter(MessageEvent.provider_event_id == provider_event_id)
                .first()
            )
            if exists:
                continue

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

            cc = cc_map.get(country_iso, "+1")
            channel_address = f"{cc}5550{index:04d}"
            contact_id = contact_cycle[index % len(contact_cycle)]
            job_id = whatsapp_job.id if whatsapp_job and index == 0 else None

            db.add(
                MessageEvent(
                    org_id=org.id,
                    message_job_id=job_id,
                    connection_id=connection.id,
                    channel="whatsapp",
                    channel_address=channel_address,
                    contact_id=contact_id,
                    provider_event_id=provider_event_id,
                    direction="outbound",
                    template_name=template_name,
                    category=category,
                    country_iso=country_iso,
                    phone_cc=cc,
                    timestamp_provider=now - timedelta(days=index % 7),
                    delivery_status="delivered",
                    unit_cost_minor=unit_cost_minor,
                    baseline_cost_minor=baseline_cost_minor,
                    currency=currency,
                )
            )

        email_events = [
            {
                "provider_event_id": "email_evt_seed_01",
                "template_name": "welcome_email",
                "delivery_status": "delivered",
                "timestamp": now - timedelta(hours=3),
                "baseline_cost_minor": DEFAULT_EMAIL_UNIT_COST_MINOR + 20,
                "attributes": {
                    "subject": "Bem-vinda ao piloto",
                    "from": DEFAULT_EMAIL_FROM_ADDRESS,
                },
            },
            {
                "provider_event_id": "email_evt_seed_02",
                "template_name": "reactivation_email",
                "delivery_status": "bounced",
                "timestamp": now - timedelta(hours=9),
                "baseline_cost_minor": DEFAULT_EMAIL_UNIT_COST_MINOR + 15,
                "attributes": {
                    "subject": "Sua conta quase lá",
                    "from": DEFAULT_EMAIL_FROM_ADDRESS,
                },
            },
        ]

        for event_data in email_events:
            exists = (
                db.query(MessageEvent)
                .filter(MessageEvent.provider_event_id == event_data["provider_event_id"])
                .first()
            )
            if exists:
                continue

            db.add(
                MessageEvent(
                    org_id=org.id,
                    message_job_id=email_job.id if email_job else None,
                    channel="email",
                    channel_address=DEFAULT_CONTACT_EMAIL,
                    contact_id=demo_contact.id,
                    provider_event_id=event_data["provider_event_id"],
                    direction="outbound",
                    template_name=event_data["template_name"],
                    category="MARKETING",
                    country_iso="GLOBAL",
                    timestamp_provider=event_data["timestamp"],
                    delivery_status=event_data["delivery_status"],
                    unit_cost_minor=DEFAULT_EMAIL_UNIT_COST_MINOR,
                    baseline_cost_minor=event_data["baseline_cost_minor"],
                    currency="USD",
                    attributes=event_data["attributes"],
                )
            )

        sms_events = [
            {
                "provider_event_id": "sms_evt_seed_01",
                "delivery_status": "delivered",
                "timestamp": now - timedelta(hours=2),
                "baseline_cost_minor": DEFAULT_SMS_UNIT_COST_MINOR + 60,
                "attributes": {"provider_sid": "SM-SEED-01"},
            },
            {
                "provider_event_id": "sms_evt_seed_02",
                "delivery_status": "failed",
                "timestamp": now - timedelta(hours=6),
                "baseline_cost_minor": DEFAULT_SMS_UNIT_COST_MINOR + 40,
                "attributes": {"provider_sid": "SM-SEED-02"},
            },
        ]

        for event_data in sms_events:
            exists = (
                db.query(MessageEvent)
                .filter(MessageEvent.provider_event_id == event_data["provider_event_id"])
                .first()
            )
            if exists:
                continue

            db.add(
                MessageEvent(
                    org_id=org.id,
                    message_job_id=sms_job.id if sms_job else None,
                    channel="sms",
                    channel_address=DEFAULT_MARKETING_CONTACT_PHONE,
                    contact_id=marketing_contact.id,
                    provider_event_id=event_data["provider_event_id"],
                    direction="outbound",
                    template_name="promo_sms",
                    category="MARKETING",
                    country_iso="BR",
                    phone_cc="+55",
                    timestamp_provider=event_data["timestamp"],
                    delivery_status=event_data["delivery_status"],
                    unit_cost_minor=DEFAULT_SMS_UNIT_COST_MINOR,
                    baseline_cost_minor=event_data["baseline_cost_minor"],
                    currency="USD",
                    attributes=event_data["attributes"],
                )
            )

        conversation = (
            db.query(Conversation)
            .filter(Conversation.org_id == org.id)
            .filter(Conversation.channel == "whatsapp")
            .filter(Conversation.channel_address == DEFAULT_CONTACT_PHONE)
            .order_by(Conversation.opened_at.desc())
            .first()
        )

        if not conversation:
            conversation_opened = now - timedelta(hours=2)
            conversation_response = conversation_opened + timedelta(minutes=10)
            conversation_closed = conversation_opened + timedelta(minutes=45)
            conversation = Conversation(
                org_id=org.id,
                contact_id=demo_contact.id,
                channel="whatsapp",
                channel_address=DEFAULT_CONTACT_PHONE,
                status=ConversationStatusEnum.closed,
                opened_at=conversation_opened,
                last_inbound_at=conversation_opened,
                first_response_at=conversation_response,
                first_response_latency_seconds=600,
                last_outbound_at=conversation_closed,
                closed_at=conversation_closed,
            )
            db.add(conversation)
            db.flush()

            queue_entry = QueueEntry(
                org_id=org.id,
                conversation_id=conversation.id,
                channel="whatsapp",
                status=QueueStatusEnum.closed,
                opened_at=conversation_opened,
                responded_at=conversation_response,
                closed_at=conversation_closed,
                first_response_latency_seconds=conversation.first_response_latency_seconds,
                total_duration_seconds=int(
                    (conversation_closed - conversation_opened).total_seconds()
                ),
            )
            db.add(queue_entry)

            snapshot_start = (now - timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            existing_snapshot = (
                db.query(SlaSnapshot)
                .filter(SlaSnapshot.org_id == org.id)
                .filter(SlaSnapshot.channel == "whatsapp")
                .filter(SlaSnapshot.period_start == snapshot_start)
                .first()
            )
            if not existing_snapshot:
                db.add(
                    SlaSnapshot(
                        org_id=org.id,
                        channel="whatsapp",
                        period_start=snapshot_start,
                        period_end=snapshot_start + timedelta(days=1),
                        sla_target_seconds=900,
                        conversations_opened=1,
                        conversations_closed=1,
                        first_response_avg_seconds=conversation.first_response_latency_seconds,
                        first_response_within_target=1,
                        backlog_open=1,
                        backlog_closed=1,
                        backlog_pending=0,
                    )
                )

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
