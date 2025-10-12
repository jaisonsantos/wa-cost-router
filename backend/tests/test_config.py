from app.core.config import Settings


def test_marketing_quiet_hours_disabled_by_default_for_local_env():
    settings = Settings(_env_file=None, ENVIRONMENT="local")

    assert settings.MARKETING_SILENT_HOURS_UTC == []


def test_marketing_quiet_hours_default_preserved_for_production_env():
    settings = Settings(_env_file=None, ENVIRONMENT="production")

    assert settings.MARKETING_SILENT_HOURS_UTC == ["22:00-06:00"]


def test_marketing_quiet_hours_respects_explicit_override_even_in_local_env():
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="local",
        MARKETING_SILENT_HOURS_UTC=["01:00-02:00"],
    )

    assert settings.MARKETING_SILENT_HOURS_UTC == ["01:00-02:00"]
