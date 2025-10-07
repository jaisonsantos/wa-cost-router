from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import logging
from app.core.database import get_db
from app.core.security import encrypt_token
from app.api.dependencies import get_current_user
from app.models.models import WAConnection, MessageEvent
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

class ConnectionCreate(BaseModel):
    business_id: str
    phone_id: str
    access_token: str
    webhook_verify_token: str
    webhook_secret: str

@router.post("/wa/connections")
def create_connection(
    data: ConnectionCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    encrypted_token = encrypt_token(data.access_token)
    encrypted_secret = encrypt_token(data.webhook_secret)
    conn = WAConnection(
        org_id=current_user["org_id"],
        business_id=data.business_id,
        phone_id=data.phone_id,
        access_token_enc=encrypted_token,
        webhook_verify_token=data.webhook_verify_token,
        webhook_secret_enc=encrypted_secret,
        status="active"
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return {"id": str(conn.id), "status": "active"}

@router.get("/wa/webhook")
def webhook_verify(
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge")
):
    if mode == "subscribe" and token == settings.WA_VERIFY_TOKEN:
        return int(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/wa/webhook")
async def webhook_receive(request: Request, db: Session = Depends(get_db)):
    body = await request.json()

    # Extract basic fields - adjust based on actual WhatsApp webhook structure
    processed = 0
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])

            for msg in messages:
                provider_id = msg.get("id")
                if not provider_id:
                    continue

                phone_id = msg.get("from") or value.get("metadata", {}).get("phone_number_id")
                connection = None
                if phone_id:
                    connection = (
                        db.query(WAConnection)
                        .filter(
                            WAConnection.phone_id == phone_id,
                            WAConnection.status == "active",
                        )
                        .first()
                    )

                if not connection:
                    connection = (
                        db.query(WAConnection)
                        .filter(WAConnection.status == "active")
                        .first()
                    )

                if not connection:
                    logger.warning("Webhook received message %s but no WA connection is configured", provider_id)
                    continue

                # Check idempotency
                existing = db.query(MessageEvent).filter(
                    MessageEvent.provider_event_id == provider_id
                ).first()
                if existing:
                    continue

                # Create event (simplified - adjust fields as needed)
                event = MessageEvent(
                    org_id=connection.org_id,
                    connection_id=connection.id,
                    provider_event_id=provider_id,
                    direction="inbound",
                    timestamp_provider=datetime.utcnow(),
                    delivery_status="received",
                    attributes=msg,
                )
                db.add(event)
                processed += 1

    db.commit()
    return {"status": "ok", "processed": processed}

@router.post("/wa/test")
def test_send(current_user: dict = Depends(get_current_user)):
    return {"status": "ok", "message": "Test endpoint - no actual send"}
