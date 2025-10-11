import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pytest
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import UUID as PGUUID

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.security import encrypt_credentials  # noqa: E402
from app.models.models import (  # noqa: E402
    Contact,
    ContactChannelOptIn,
    ContactStatusEnum,
    OptInStatusEnum,
    Organization,
    Provider,
    ProviderCredential,
    RateCard,
    RoutingRule,
)


PHONE_CHANNELS = {"whatsapp", "sms"}


@compiles(PGUUID, "sqlite")
def compile_uuid_sqlite(element, compiler, **kwargs):  # pragma: no cover - SQLAlchemy hook
    return "CHAR(36)"


@pytest.fixture
def organization_factory(db_session):
    def _create(*, org_id: uuid.UUID, name: str = "Test Org") -> Organization:
        existing = (
            db_session.query(Organization)
            .filter(Organization.id == org_id)
            .first()
        )
        if existing:
            return existing

        organization = Organization(id=org_id, name=name)
        db_session.add(organization)
        db_session.commit()
        return organization

    return _create


@pytest.fixture
def provider_factory(db_session):
    def _create(
        *,
        org_id: uuid.UUID,
        name: str,
        provider_type: str,
        channel: str,
        unit_cost_minor: int,
        country_iso: str,
        template_category: str = "MARKETING",
        currency: str = "USD",
        meta: Optional[Dict[str, Any]] = None,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Provider:
        provider = Provider(
            org_id=org_id,
            name=name,
            type=provider_type,
            status="active",
            meta=meta or {},
        )
        db_session.add(provider)
        db_session.flush()

        credential_payload = credentials or {"api_key": f"{name}-token"}
        credential = ProviderCredential(
            org_id=org_id,
            provider_id=provider.id,
            credentials_encrypted=encrypt_credentials(credential_payload),
            is_active=True,
        )
        db_session.add(credential)

        rate = RateCard(
            provider_id=provider.id,
            effective_from=datetime.utcnow(),
            source="test",
            country_iso=country_iso,
            category=template_category,
            unit_cost_minor=unit_cost_minor,
            currency=currency,
        )
        db_session.add(rate)
        db_session.commit()

        return provider

    return _create


@pytest.fixture
def routing_rule_factory(db_session):
    def _create(
        *,
        org_id: uuid.UUID,
        channel: str,
        providers: Iterable[Provider],
        template_category: str = "MARKETING",
        conditions: Optional[List[Dict[str, Any]]] = None,
        priority: int = 10,
    ) -> RoutingRule:
        provider_list = list(providers)
        if not provider_list:
            raise ValueError("At least one provider is required to create a routing rule")

        actions = {
            "channel": channel,
            "primary_provider": str(provider_list[0].id),
            "fallback_chain": [str(provider.id) for provider in provider_list[1:]],
        }

        rule = RoutingRule(
            org_id=org_id,
            name=f"route-{channel}-{uuid.uuid4().hex[:6]}",
            is_enabled=True,
            conditions_json=conditions
            if conditions is not None
            else [{"type": "category", "values": [template_category]}],
            actions_json=actions,
            priority=priority,
        )
        db_session.add(rule)
        db_session.commit()
        return rule

    return _create


@pytest.fixture
def contact_factory(db_session):
    def _create(
        *,
        org_id: uuid.UUID,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        status: ContactStatusEnum = ContactStatusEnum.active,
        opt_ins: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> Contact:
        contact = Contact(
            id=uuid.uuid4(),
            org_id=org_id,
            phone=phone,
            email=email,
            status=status,
        )
        db_session.add(contact)
        db_session.flush()

        if opt_ins:
            for opt_in in opt_ins:
                channel = opt_in.get("channel")
                if channel is None:
                    raise ValueError("opt_in payload must include channel")
                normalized_channel = channel.lower()
                address = opt_in.get("channel_address")
                if not address:
                    if normalized_channel in PHONE_CHANNELS:
                        address = phone
                    else:
                        address = email
                if not address:
                    raise ValueError("Unable to infer channel address for opt-in")
                record = ContactChannelOptIn(
                    org_id=org_id,
                    contact_id=contact.id,
                    channel=normalized_channel,
                    channel_address=address,
                    status=opt_in.get("status", OptInStatusEnum.granted),
                    version=opt_in.get("version", 1),
                    source=opt_in.get("source", "test"),
                )
                db_session.add(record)

        db_session.commit()
        return contact

    return _create


@pytest.fixture
def email_provider_seed(provider_factory, db_session):
    def _create(
        *,
        org_id: uuid.UUID,
        token: str = "email-token",
        signing_secret: str = "email-secret",
        unit_cost_minor: int = 75,
    ) -> Dict[str, Any]:
        provider = provider_factory(
            org_id=org_id,
            name="SendGrid Sandbox",
            provider_type="email",
            channel="email",
            unit_cost_minor=unit_cost_minor,
            country_iso="XX",
            meta={},
            credentials={
                "api_key": "sg-test",
                "webhook_token": token,
                "inbound_signing_secret": signing_secret,
            },
        )

        credential = (
            db_session.query(ProviderCredential)
            .filter(ProviderCredential.provider_id == provider.id)
            .filter(ProviderCredential.org_id == org_id)
            .first()
        )

        return {
            "provider": provider,
            "credential": credential,
            "token": token,
            "signing_secret": signing_secret,
        }

    return _create


@pytest.fixture
def sms_provider_seed(provider_factory, db_session):
    def _create(
        *,
        org_id: uuid.UUID,
        number: str = "+15558675309",
        auth_token: str = "sms-secret",
        unit_cost_minor: int = 140,
    ) -> Dict[str, Any]:
        provider = provider_factory(
            org_id=org_id,
            name="Twilio Sandbox",
            provider_type="sms",
            channel="sms",
            unit_cost_minor=unit_cost_minor,
            country_iso="BR",
            meta={
                "channels": {"sms": {"inbound_numbers": [number]}},
            },
            credentials={
                "account_sid": "AC123456789",
                "auth_token": auth_token,
                "from_number": number,
                "inbound_verify_token": "sms-verify",
            },
        )

        credential = (
            db_session.query(ProviderCredential)
            .filter(ProviderCredential.provider_id == provider.id)
            .filter(ProviderCredential.org_id == org_id)
            .first()
        )

        return {
            "provider": provider,
            "credential": credential,
            "auth_token": auth_token,
            "number": number,
        }

    return _create
