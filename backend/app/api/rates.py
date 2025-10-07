from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import csv
import io
from app.core.database import get_db
from app.api.dependencies import get_current_user
from uuid import UUID
from app.models.models import RateCard, Provider

router = APIRouter()

class RateResponse(BaseModel):
    id: str
    provider_id: str
    provider_name: str
    effective_from: datetime
    country_iso: str
    category: str
    template_name: Optional[str] = None
    unit_cost_minor: int
    currency: str

@router.get("/", response_model=list[RateResponse])
def list_rates(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    rates = (
        db.query(RateCard, Provider)
        .join(Provider, RateCard.provider_id == Provider.id)
        .filter(Provider.org_id == current_user["org_id"])
        .order_by(RateCard.effective_from.desc())
        .limit(100)
        .all()
    )
    return [
        RateResponse(
            id=str(rate.id),
            provider_id=str(provider.id),
            provider_name=provider.name,
            effective_from=rate.effective_from,
            country_iso=rate.country_iso,
            category=rate.category,
            template_name=rate.template_name,
            unit_cost_minor=rate.unit_cost_minor,
            currency=rate.currency,
        )
        for rate, provider in rates
    ]

@router.post("/import_csv")
async def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    
    count = 0
    for row in reader:
        try:
            provider_identifier = row.get("provider_id") or row.get("provider_name")
        except KeyError:
            provider_identifier = None

        if not provider_identifier:
            raise HTTPException(
                status_code=400,
                detail="CSV must include provider_id or provider_name column",
            )

        provider = None
        try:
            provider_uuid = UUID(str(provider_identifier))
        except ValueError:
            provider = (
                db.query(Provider)
                .filter(
                    Provider.org_id == current_user["org_id"],
                    func.lower(Provider.name) == str(provider_identifier).strip().lower(),
                )
                .first()
            )
            if not provider:
                raise HTTPException(
                    status_code=404,
                    detail=f"Provider {provider_identifier} not found",
                )
            provider_uuid = provider.id
        else:
            provider = (
                db.query(Provider)
                .filter(
                    Provider.id == provider_uuid,
                    Provider.org_id == current_user["org_id"],
                )
                .first()
            )
            if not provider:
                raise HTTPException(
                    status_code=404,
                    detail=f"Provider {provider_identifier} not found",
                )

        rate = RateCard(
            provider_id=provider_uuid,
            effective_from=datetime.fromisoformat(row["effective_from"]),
            source="csv_import",
            country_iso=row["country_iso"],
            category=row["category"],
            template_name=row.get("template_name") or None,
            unit_cost_minor=int(row["unit_cost_minor"]),
            currency=row["currency"],
            notes=row.get("notes")
        )
        db.add(rate)
        count += 1
    
    db.commit()
    return {"imported": count}
