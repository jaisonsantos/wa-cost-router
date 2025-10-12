from __future__ import annotations

from typing import Dict

from app.services.provider_registry import (
    get_provider_profile,
    validate_provider_credentials,
)


def test_twilio_profile_merges_metadata():
    provider_meta: Dict[str, object] = {
        "channels": {
            "sms": {
                "inbound_numbers": ["+15550000000"],
            }
        }
    }

    profile = get_provider_profile("sms", "Twilio Sandbox", provider_meta)

    assert "account_sid" in profile.required_fields
    assert profile.metadata["channels"]["sms"]["inbound_numbers"] == ["+15550000000"]

    field_keys = {field["key"] for field in profile.form_schema.get("fields", [])}
    assert {"account_sid", "auth_token", "from_number"}.issubset(field_keys)


def test_validate_credentials_flags_missing_and_invalid_values():
    invalid = {
        "account_sid": "AC123",
        "auth_token": "short",
        "from_number": "1234",
    }

    errors = validate_provider_credentials("sms", invalid, provider_name="Twilio")
    assert any("Account SID" in error for error in errors)
    assert any("Auth Token" in error for error in errors)
    assert any("E.164" in error for error in errors)


def test_validate_credentials_accepts_valid_payload():
    credentials = {
        "account_sid": "AC" + "X" * 31,
        "auth_token": "demo-sms-auth-token",
        "from_number": "+15558675309",
        "inbound_verify_token": "sandbox-token",
    }

    errors = validate_provider_credentials(
        "sms",
        credentials,
        provider_name="Twilio",
    )

    assert errors == []


def test_validate_credentials_accepts_sms_without_plus_prefix():
    credentials = {
        "account_sid": "AC" + "0" * 32,
        "auth_token": "sandbox-twilio-auth-token",
        "from_number": "15558675309",
    }

    errors = validate_provider_credentials(
        "sms",
        credentials,
        provider_name="Twilio",
    )

    assert errors == []


def test_validate_credentials_accepts_demo_sendgrid_payload():
    credentials = {
        "api_key": "SG.demo-api-key",
        "from_email": "no-reply+sandbox@example.com",
        "webhook_token": "demo-email-webhook-token",
        "inbound_signing_secret": "demo-email-webhook-secret",
    }

    errors = validate_provider_credentials(
        "email",
        credentials,
        provider_name="SendGrid",
    )

    assert errors == []


def test_validate_credentials_accepts_sandbox_sendgrid_token():
    credentials = {
        "api_key": "sandbox-sendgrid-api-key",
        "from_email": "no-reply+sandbox@example.com",
        "webhook_token": "demo-email-webhook-token",
        "inbound_signing_secret": "demo-email-webhook-secret",
    }

    errors = validate_provider_credentials(
        "email",
        credentials,
        provider_name="SendGrid",
    )

    assert errors == []


def test_sendgrid_profile_includes_required_fields():
    profile = get_provider_profile("email", "SendGrid Sandbox", {})

    assert set(profile.required_fields) == {
        "api_key",
        "from_email",
        "inbound_signing_secret",
        "webhook_token",
    }

    validation_errors = validate_provider_credentials(
        "email",
        {
            "api_key": "SG.invalid",
            "from_email": "invalid",
            "webhook_token": "short",
            "inbound_signing_secret": "123",
        },
        provider_name="SendGrid",
    )

    assert len(validation_errors) >= 3

