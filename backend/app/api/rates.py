from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import csv
import io
from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.models import RateCard

router = APIRouter()

class RateResponse(BaseModel):
    id: str
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
    rates = db.query(RateCard).order_by(RateCard.effective_from.desc()).limit(100).all()
    return [
        RateResponse(
            id=str(r.id),
            effective_from=r.effective_from,
            country_iso=r.country_iso,
            category=r.category,
            template_name=r.template_name,
            unit_cost_minor=r.unit_cost_minor,
            currency=r.currency
        )
        for r in rates
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
        rate = RateCard(
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
