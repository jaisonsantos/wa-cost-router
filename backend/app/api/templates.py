import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.security import decrypt_credentials
from app.models.models import Provider, ProviderCredential, WATemplate
from app.services.provider_connectors import get_connector

def _deduplicate_preserve_order(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _sanitize_country_list(raw: Any) -> Optional[List[str]]:
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes)):
        return None
    normalized: List[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        candidate = item.strip().upper()
        if len(candidate) in {2, 3} and candidate.isalpha():
            normalized.append(candidate)
    if not normalized:
        return None
    return _deduplicate_preserve_order(normalized)


def _sanitize_hour_windows(raw: Any) -> Optional[List[str]]:
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes)):
        return None
    windows: List[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        try:
            start_raw, end_raw = item.split("-", 1)
            start_time = datetime.strptime(start_raw.strip(), "%H:%M").time()
            end_time = datetime.strptime(end_raw.strip(), "%H:%M").time()
        except (ValueError, AttributeError):
            logger.debug("Ignoring invalid template hour window: %r", item)
            continue
        windows.append(f"{start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}")
    if not windows:
        return None
    return _deduplicate_preserve_order(windows)


def _sanitize_template_meta(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}

    sanitized: Dict[str, Any] = {}

    blocked_countries = _sanitize_country_list(raw.get("blocked_countries"))
    if blocked_countries:
        sanitized["blocked_countries"] = blocked_countries

    allowed_countries = _sanitize_country_list(raw.get("allowed_countries"))
    if allowed_countries:
        sanitized["allowed_countries"] = allowed_countries

    blocked_hours = _sanitize_hour_windows(raw.get("blocked_hours"))
    if blocked_hours:
        sanitized["blocked_hours"] = blocked_hours

    allowed_hours = _sanitize_hour_windows(raw.get("allowed_hours"))
    if allowed_hours:
        sanitized["allowed_hours"] = allowed_hours

    return sanitized
logger = logging.getLogger(__name__)
router = APIRouter()


class TemplateResponse(BaseModel):
    id: str
    name: str
    category: str
    language: str
    status: str
    meta: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True

    @field_validator("meta", mode="before")
    @classmethod
    def _ensure_meta(cls, value: Any) -> Dict[str, Any]:
        return _sanitize_template_meta(value)

    @field_validator("id", mode="before")
    @classmethod
    def _stringify_id(cls, value: Any) -> str:
        return str(value)


class TemplateCreatePayload(BaseModel):
    name: str
    category: str
    language: str
    status: str
    meta: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _sanitize_meta(self) -> "TemplateCreatePayload":
        self.meta = _sanitize_template_meta(self.meta)
        return self


class TemplateUpdatePayload(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    status: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def _sanitize_meta(self) -> "TemplateUpdatePayload":
        if self.meta is not None:
            self.meta = _sanitize_template_meta(self.meta)
        return self


class TemplateSyncProviderSummary(BaseModel):
    provider: str
    total_templates: int
    languages: List[str]
    statuses: List[str]
    error: Optional[str] = None


class TemplateSyncResponse(BaseModel):
    synced: int
    providers: List[TemplateSyncProviderSummary]
    languages: List[str]
    statuses: List[str]


@router.get("/", response_model=List[TemplateResponse])
def list_templates(
    *,
    language: Optional[str] = Query(default=None, description="Filtro por idioma (ex.: en_US)"),
    status: Optional[str] = Query(default=None, description="Filtro por status (ex.: approved)"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[TemplateResponse]:
    query = db.query(WATemplate).filter(WATemplate.org_id == current_user["org_id"])

    if language:
        query = query.filter(func.lower(WATemplate.language) == language.lower())
    if status:
        query = query.filter(func.lower(WATemplate.status) == status.lower())

    templates = query.order_by(WATemplate.name.asc()).all()
    return [TemplateResponse.model_validate(template) for template in templates]


@router.post("/", response_model=TemplateResponse, status_code=201)
def create_template(
    payload: TemplateCreatePayload,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TemplateResponse:
    template = WATemplate(
        org_id=current_user["org_id"],
        name=payload.name,
        category=payload.category,
        language=payload.language,
        status=payload.status,
        meta=payload.meta or {},
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return TemplateResponse.model_validate(template)


@router.patch("/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: str,
    payload: TemplateUpdatePayload,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TemplateResponse:
    try:
        template_uuid = UUID(template_id)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=400, detail="Invalid template id") from exc

    template = (
        db.query(WATemplate)
        .filter(
            WATemplate.id == template_uuid,
            WATemplate.org_id == current_user["org_id"],
        )
        .first()
    )
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(template, field, value)

    db.commit()
    db.refresh(template)
    return TemplateResponse.model_validate(template)


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> None:
    try:
        template_uuid = UUID(template_id)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=400, detail="Invalid template id") from exc

    deleted = (
        db.query(WATemplate)
        .filter(
            WATemplate.id == template_uuid,
            WATemplate.org_id == current_user["org_id"],
        )
        .delete()
    )
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    db.commit()


@router.post("/sync", response_model=TemplateSyncResponse)
async def sync_templates(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TemplateSyncResponse:
    providers = (
        db.query(Provider)
        .filter(
            Provider.org_id == current_user["org_id"],
            Provider.type.in_(["whatsapp", "meta", "whatsapp_cloud"]),
            Provider.status == "active",
        )
        .all()
    )

    summaries: List[TemplateSyncProviderSummary] = []
    aggregated_languages: set[str] = set()
    aggregated_statuses: set[str] = set()
    total_synced = 0

    for provider in providers:
        credential = (
            db.query(ProviderCredential)
            .filter(
                ProviderCredential.org_id == current_user["org_id"],
                ProviderCredential.provider_id == provider.id,
                ProviderCredential.is_active.is_(True),
            )
            .first()
        )

        if credential is None:
            summaries.append(
                TemplateSyncProviderSummary(
                    provider=provider.name,
                    total_templates=0,
                    languages=[],
                    statuses=[],
                    error="No active credentials configured",
                )
            )
            continue

        credentials = decrypt_credentials(credential.credentials_encrypted)

        try:
            connector = get_connector(
                provider.name,
                credentials,
                provider.base_url,
                provider_type=provider.type,
                sandbox_options=(provider.meta or {}).get("sandbox"),
            )
            templates = await connector.list_templates()
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to sync templates for provider %s", provider.name)
            summaries.append(
                TemplateSyncProviderSummary(
                    provider=provider.name,
                    total_templates=0,
                    languages=[],
                    statuses=[],
                    error=str(exc),
                )
            )
            continue

        provider_languages: set[str] = set()
        provider_statuses: set[str] = set()
        provider_total = 0

        for template_payload in templates or []:
            name = template_payload.get("name")
            if not name:
                continue

            language = template_payload.get("language") or "en_US"
            status_value = template_payload.get("status") or "pending"
            category = template_payload.get("category") or "marketing"
            metadata = _sanitize_template_meta(template_payload.get("meta"))

            provider_languages.add(language)
            provider_statuses.add(status_value)
            aggregated_languages.add(language)
            aggregated_statuses.add(status_value)

            existing = (
                db.query(WATemplate)
                .filter(
                    WATemplate.org_id == current_user["org_id"],
                    func.lower(WATemplate.name) == name.lower(),
                    func.lower(WATemplate.language) == language.lower(),
                )
                .first()
            )

            if existing:
                existing.category = category
                existing.status = status_value
                existing.meta = metadata
            else:
                new_template = WATemplate(
                    org_id=current_user["org_id"],
                    name=name,
                    category=category,
                    language=language,
                    status=status_value,
                    meta=metadata,
                )
                db.add(new_template)

            provider_total += 1

        summaries.append(
            TemplateSyncProviderSummary(
                provider=provider.name,
                total_templates=provider_total,
                languages=sorted(provider_languages),
                statuses=sorted(provider_statuses),
            )
        )
        total_synced += provider_total

    if total_synced:
        db.commit()
    else:
        db.rollback()

    return TemplateSyncResponse(
        synced=total_synced,
        providers=summaries,
        languages=sorted(aggregated_languages),
        statuses=sorted(aggregated_statuses),
    )
