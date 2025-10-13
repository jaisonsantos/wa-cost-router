from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    billing,
    auth,
    events,
    integrations,
    integrations_crm,
    integrations_email,
    integrations_sms,
    messages,
    opt_in,
    orgs,
    providers,
    rates,
    reports,
    rules,
    templates,
)
from app.api.routes import contact_segments, contacts
from app.core.config import Settings, settings


_LOCAL_DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]


def _determine_cors_origins(settings: Settings) -> list[str]:
    environment = (settings.ENVIRONMENT or "").lower()
    configured = [origin for origin in settings.API_CORS_ORIGINS if origin]

    defaults: list[str] = []
    if environment in {"local", "dev", "development", "test", "testing"}:
        defaults = _LOCAL_DEFAULT_CORS_ORIGINS

    combined: list[str] = []
    for origin in (*configured, *defaults):
        if origin and origin not in combined:
            combined.append(origin)

    return combined


def create_app(settings: Settings = settings) -> FastAPI:
    app = FastAPI(title="WA Cost Router API", version="1.0.0")

    allowed_origins = _determine_cors_origins(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(orgs.router, prefix="/orgs", tags=["orgs"])
    app.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
    app.include_router(
        integrations_sms.router,
        prefix="/integrations/sms",
        tags=["integrations"],
    )
    app.include_router(
        integrations_email.router,
        prefix="/integrations/email",
        tags=["integrations"],
    )
    app.include_router(
        integrations_crm.router,
        prefix="/integrations/crm",
        tags=["integrations:crm"],
    )
    app.include_router(rates.router, prefix="/rates", tags=["rates"])
    app.include_router(events.router, prefix="/events", tags=["events"])
    app.include_router(reports.router, prefix="/reports", tags=["reports"])
    app.include_router(rules.router, prefix="/rules", tags=["rules"])
    app.include_router(admin.router, prefix="/admin", tags=["admin"])
    app.include_router(messages.router, prefix="/messages", tags=["messages"])
    app.include_router(providers.router, prefix="/providers", tags=["providers"])
    app.include_router(templates.router, prefix="/templates", tags=["templates"])
    app.include_router(contacts.router, prefix="/contacts", tags=["contacts"])
    app.include_router(
        contact_segments.router,
        prefix="/contact-segments",
        tags=["contact_segments"],
    )
    app.include_router(opt_in.router, prefix="/opt-in", tags=["opt_in"])
    app.include_router(billing.router, prefix="/billing", tags=["billing"])

    @app.get("/")
    def read_root():
        return {"message": "WA Cost Router API", "version": "1.0.0"}

    return app

app = create_app()
