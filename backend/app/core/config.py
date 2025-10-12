from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    METRICS_AUTH_TOKEN: str | None = None
    METRICS_AUTH_HEADER_NAME: str = "X-Admin-Token"
    METRICS_AUTH_LOCAL_TOKEN: str = "local-admin-metrics-token"

    def get_metrics_auth_token(self) -> str | None:
        token = self.METRICS_AUTH_TOKEN
        if token:
            return token

        environment = (self.ENVIRONMENT or "").lower()
        if environment in {"local", "dev", "development", "test", "testing"}:
            return self.METRICS_AUTH_LOCAL_TOKEN

        return None


settings = Settings()
