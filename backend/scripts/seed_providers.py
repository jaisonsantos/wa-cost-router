"""
Script para popular providers iniciais
"""
from app.core.database import SessionLocal
from app.models.models import Provider

def seed_providers():
    db = SessionLocal()
    
    try:
        # Verificar se já existem
        existing = db.query(Provider).count()
        if existing > 0:
            print(f"Providers already seeded ({existing} providers)")
            return
        
        # Criar providers padrão
        providers = [
            Provider(
                name="360dialog",
                type="whatsapp",
                base_url="https://waba.360dialog.io/v1",
                status="active",
                metadata={"description": "360Dialog WhatsApp Business API"}
            ),
            Provider(
                name="gupshup",
                type="whatsapp",
                base_url="https://api.gupshup.io/sm/api/v1",
                status="active",
                metadata={"description": "Gupshup WhatsApp Business API"}
            )
        ]
        
        for provider in providers:
            db.add(provider)
        
        db.commit()
        print(f"✅ Seeded {len(providers)} providers")
    
    except Exception as e:
        print(f"❌ Error seeding providers: {str(e)}")
        db.rollback()
    
    finally:
        db.close()

if __name__ == "__main__":
    seed_providers()
