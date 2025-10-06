from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.models import MessageEvent

router = APIRouter()

class EventResponse(BaseModel):
    id: str
    direction: str
    template_name: Optional[str]
    category: Optional[str]
    country_iso: Optional[str]
    timestamp_provider: datetime
    delivery_status: Optional[str]
    unit_cost_minor: Optional[int]
    currency: Optional[str]

@router.get("/", response_model=list[EventResponse])
def list_events(
    limit: int = Query(50, le=1000),
    offset: int = Query(0),
    country: Optional[str] = None,
    template: Optional[str] = None,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(MessageEvent).filter(MessageEvent.org_id == current_user["org_id"])
    
    if country:
        query = query.filter(MessageEvent.country_iso == country)
    if template:
        query = query.filter(MessageEvent.template_name == template)
    if from_date:
        query = query.filter(MessageEvent.timestamp_provider >= datetime.fromisoformat(from_date))
    if to_date:
        query = query.filter(MessageEvent.timestamp_provider <= datetime.fromisoformat(to_date))
    
    events = query.order_by(MessageEvent.timestamp_provider.desc()).offset(offset).limit(limit).all()
    
    return [
        EventResponse(
            id=str(e.id),
            direction=e.direction,
            template_name=e.template_name,
            category=e.category,
            country_iso=e.country_iso,
            timestamp_provider=e.timestamp_provider,
            delivery_status=e.delivery_status,
            unit_cost_minor=e.unit_cost_minor,
            currency=e.currency
        )
        for e in events
    ]
