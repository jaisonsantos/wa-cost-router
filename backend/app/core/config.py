from pydantic_settings import BaseSettings

class Settings(BaseSettings):
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
    
    class Config:
        env_file = ".env"

settings = Settings()
