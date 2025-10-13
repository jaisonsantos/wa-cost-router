import pytest

from app.core.config import Settings


def test_marketing_quiet_hours_disabled_by_default_for_local_env():
    settings = Settings(_env_file=None, ENVIRONMENT="local")

    assert settings.MARKETING_SILENT_HOURS_UTC == []


def test_marketing_quiet_hours_default_preserved_for_production_env():
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        JWT_SECRET="prod-secret",
        APP_SECRET_KEY="prod-app-secret",
    )

    assert settings.MARKETING_SILENT_HOURS_UTC == ["22:00-06:00"]


def test_marketing_quiet_hours_respects_explicit_override_even_in_local_env():
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="local",
        MARKETING_SILENT_HOURS_UTC=["01:00-02:00"],
    )

    assert settings.MARKETING_SILENT_HOURS_UTC == ["01:00-02:00"]


@pytest.mark.parametrize("environment", ["local", "development", "test"])
def test_default_secrets_allowed_in_non_production_environments(environment: str) -> None:
    settings = Settings(_env_file=None, ENVIRONMENT=environment)

    assert settings.JWT_SECRET
    assert settings.APP_SECRET_KEY


@pytest.mark.parametrize("environment", ["production", "staging", "qa"])
def test_default_secrets_rejected_in_hardened_environments(environment: str) -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, ENVIRONMENT=environment)


def test_custom_secrets_allowed_for_hardened_environment() -> None:
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        JWT_SECRET="super-secure",
        APP_SECRET_KEY="also-secure",
    )

    assert settings.JWT_SECRET == "super-secure"
    assert settings.APP_SECRET_KEY == "also-secure"
