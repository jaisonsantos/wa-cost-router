from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import DotEnvSettingsSource, EnvSettingsSource


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    ENVIRONMENT: str = "local"
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@db:5432/wa_cost_router"
    REDIS_URL: str = "redis://redis:6379/0"
    JWT_SECRET: str = "change-this"
    JWT_ALG: str = "HS256"
    APP_SECRET_KEY: str = "please-change-me"
    DEFAULT_ORG_TZ: str = "Europe/Madrid"

    WA_APP_SECRET: str = "fake"
    WA_VERIFY_TOKEN: str = "my-verify-token"
    META_WHATSAPP_CLOUD_ACCESS_TOKEN: str = ""
    META_WHATSAPP_CLOUD_PHONE_ID: str = ""

    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    SMTP_HOST: str = "mailhog"
    SMTP_PORT: int = 1025

    SENDGRID_API_KEY: str = ""
    SENDGRID_DEFAULT_SENDER_EMAIL: str = ""
    SENDGRID_BASE_URL: str = "https://api.sendgrid.com/v3"

    SANDBOX_PROVIDERS: bool = False
    SANDBOX_LATENCY_MS: int = 100
    SANDBOX_FAILURE_RATE: float = 0.0

    CIRCUIT_BREAKER_THRESHOLD: int = 3
    CIRCUIT_BREAKER_COOLDOWN_SECONDS: int = 60

    CRM_WEBHOOK_SECRET: str = "change-me"
    CRM_POLLING_INTERVAL_SECONDS: int = 300
    CRM_MAX_PAGE_SIZE: int = 100
    CRM_PIPEDRIVE_BASE_URL_TEMPLATE: str = "https://{company_domain}/api/v1"
    CRM_PIPEDRIVE_MAX_PAGE_SIZE: int = 500

    OPT_IN_EMAIL_TEMPLATE_ID: str = "request-whatsapp-opt-in"
    OPT_IN_MAX_ATTEMPTS: int = 3
    OPT_IN_RETRY_MINUTES: int = 120
    OPT_IN_WEBHOOK_TOKEN: str = "change-me-optin"
    CONTACTS_OPT_IN_ROLLOUT_ENABLED: bool = False
    CONTACTS_OPT_IN_ROLLOUT_TENANTS: list[str] = Field(default_factory=list)

    RATE_LIMIT_MESSAGES_PER_MIN: int = 120
    RATE_LIMIT_LOGIN_PER_MIN: int = 20

    MARKETING_SILENT_HOURS_UTC: list[str] = Field(default_factory=lambda: ["22:00-06:00"])

    API_CORS_ORIGINS: list[str] = Field(default_factory=list)

    METRICS_AUTH_TOKEN: str | None = None
    METRICS_AUTH_HEADER_NAME: str = "X-Admin-Token"
    METRICS_AUTH_LOCAL_TOKEN: str = "local-admin-metrics-token"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
        **kwargs,
    ):
        def _wrap_source(source: EnvSettingsSource | None) -> EnvSettingsSource | None:
            if source is None:
                return None

            source_cls = source.__class__

            class _BlankAwareSource(source_cls):  # type: ignore[misc, valid-type]
                def decode_complex_value(self, field_name, field, value):  # type: ignore[override]
                    if field_name == "API_CORS_ORIGINS":
                        if value is None:
                            return None
                        if isinstance(value, str):
                            stripped = value.strip()
                            if not stripped:
                                return []
                            return stripped
                    return super().decode_complex_value(field_name, field, value)

            init_kwargs: dict[str, Any] = {
                "case_sensitive": getattr(source, "case_sensitive", None),
                "env_prefix": getattr(source, "env_prefix", None),
                "env_nested_delimiter": getattr(source, "env_nested_delimiter", None),
            }

            if isinstance(source, DotEnvSettingsSource):
                init_kwargs.update(
                    {
                        "env_file": source.env_file,
                        "env_file_encoding": source.env_file_encoding,
                    }
                )

            return _BlankAwareSource(settings_cls, **init_kwargs)

        additional_sources = tuple(
            source for source in kwargs.values() if source is not None
        )

        return (
            init_settings,
            _wrap_source(env_settings),
            _wrap_source(dotenv_settings),
            file_secret_settings,
            *additional_sources,
        )

    @staticmethod
    def _normalize_cors_origins(value: Any) -> list[str] | Any:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="before")
    @classmethod
    def _preprocess_cors_origins(cls, data: Any) -> Any:
        if isinstance(data, dict) and "API_CORS_ORIGINS" in data:
            data["API_CORS_ORIGINS"] = cls._normalize_cors_origins(data["API_CORS_ORIGINS"])
        return data

    @field_validator("API_CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: Any) -> list[str] | Any:
        return cls._normalize_cors_origins(value)

    def model_post_init(self, __context: Any) -> None:  # pragma: no cover - exercised via settings singleton
        super().model_post_init(__context)

        environment = (self.ENVIRONMENT or "").lower()
        if environment in {"local", "dev", "development", "test", "testing"}:
            if "MARKETING_SILENT_HOURS_UTC" not in self.model_fields_set:
                object.__setattr__(self, "MARKETING_SILENT_HOURS_UTC", [])

    def get_metrics_auth_token(self) -> str | None:
        token = self.METRICS_AUTH_TOKEN
        if token:
            return token

        environment = (self.ENVIRONMENT or "").lower()
        if environment in {"local", "dev", "development", "test", "testing"}:
            return self.METRICS_AUTH_LOCAL_TOKEN

        return None


settings = Settings()
