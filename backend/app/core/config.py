from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@db:5432/wa_cost_router"
    REDIS_URL: str = "redis://redis:6379/0"
    JWT_SECRET: str = "change-this"
    JWT_ALG: str = "HS256"
    APP_SECRET_KEY: str = "please-change-me"
    DEFAULT_ORG_TZ: str = "Europe/Madrid"

    WA_APP_SECRET: str = "fake"
    WA_VERIFY_TOKEN: str = "my-verify-token"

    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    SMTP_HOST: str = "mailhog"
    SMTP_PORT: int = 1025

    SANDBOX_PROVIDERS: bool = False
    SANDBOX_LATENCY_MS: int = 100
    SANDBOX_FAILURE_RATE: float = 0.0

    CRM_WEBHOOK_SECRET: str = "change-me"
    CRM_POLLING_INTERVAL_SECONDS: int = 300
    CRM_MAX_PAGE_SIZE: int = 100

    OPT_IN_EMAIL_TEMPLATE_ID: str = "request-whatsapp-opt-in"
    OPT_IN_MAX_ATTEMPTS: int = 3
    OPT_IN_RETRY_MINUTES: int = 120
    OPT_IN_WEBHOOK_TOKEN: str = "change-me-optin"


settings = Settings()
