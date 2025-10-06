import sys
sys.path.insert(0, "/app")

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import random
from app.core.database import SessionLocal, engine
from app.core.security import hash_password, encrypt_token
from app.models.models import *

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Create demo org
    org = Organization(name="Demo Org")
    db.add(org)
    db.flush()
    
    # Create demo user
    user = User(email="admin@demo.local", password_hash=hash_password("demo123"))
    db.add(user)
    db.flush()
    
    # Link user to org
    org_user = OrganizationUser(org_id=org.id, user_id=user.id, role=RoleEnum.owner)
    db.add(org_user)
    
    # Create fake WA connection
    conn = WAConnection(
        org_id=org.id,
        business_id="demo_business_123",
        phone_id="demo_phone_456",
        access_token_enc=encrypt_token("fake_token_abc"),
        status="active"
    )
    db.add(conn)
    db.flush()
    
    # Create rate cards
    now = datetime.utcnow()
    rates = [
        RateCard(effective_from=now, source="seed", country_iso="BR", category="MARKETING", 
                 unit_cost_minor=85, currency="USD"),
        RateCard(effective_from=now, source="seed", country_iso="BR", category="UTILITY", 
                 unit_cost_minor=42, currency="USD"),
        RateCard(effective_from=now, source="seed", country_iso="ES", category="MARKETING", 
                 unit_cost_minor=95, currency="USD"),
        RateCard(effective_from=now, source="seed", country_iso="GLOBAL", category="MARKETING", 
                 unit_cost_minor=100, currency="USD"),
    ]
    for r in rates:
        db.add(r)
    
    # Create synthetic message events
    countries = ["BR", "ES", "US", "MX"]
    categories = ["MARKETING", "UTILITY", "AUTHENTICATION"]
    templates = ["welcome_msg", "order_confirmation", "promo_campaign"]
    
    for i in range(20):
        event = MessageEvent(
            org_id=org.id,
            connection_id=conn.id,
            provider_event_id=f"evt_{i}_{random.randint(1000,9999)}",
            direction="outbound",
            template_name=random.choice(templates),
            category=random.choice(categories),
            country_iso=random.choice(countries),
            phone_cc="+55",
            timestamp_provider=now - timedelta(days=random.randint(0, 7)),
            delivery_status="delivered"
        )
        db.add(event)
    
    db.commit()
    print("✅ Seed data created successfully!")
    db.close()

if __name__ == "__main__":
    seed()
