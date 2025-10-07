from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, orgs, integrations, rates, events, reports, rules, admin, messages, providers

app = FastAPI(title="WA Cost Router API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(orgs.router, prefix="/orgs", tags=["orgs"])
app.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
app.include_router(rates.router, prefix="/rates", tags=["rates"])
app.include_router(events.router, prefix="/events", tags=["events"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(rules.router, prefix="/rules", tags=["rules"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(messages.router, prefix="/messages", tags=["messages"])
app.include_router(providers.router, prefix="/providers", tags=["providers"])

@app.get("/")
def read_root():
    return {"message": "WA Cost Router API", "version": "1.0.0"}
