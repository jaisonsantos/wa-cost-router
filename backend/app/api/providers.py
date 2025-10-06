from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.models import Provider, ProviderCredential
from app.services.provider_connectors import get_connector
from app.core.security import encrypt_credentials, decrypt_credentials
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class ProviderCreate(BaseModel):
    name: str
    type: str = "whatsapp"
    base_url: Optional[str] = None
    metadata: Dict[str, Any] = {}

class ProviderCredentialCreate(BaseModel):
    provider_id: str
    credentials: Dict[str, Any]

class ProviderResponse(BaseModel):
    id: str
    name: str
    type: str
    status: str
    is_configured: bool
    has_credentials: bool
    avg_latency_ms: Optional[float] = None

@router.get("/", response_model=List[ProviderResponse])
def list_providers(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lista todos os provedores disponíveis para a org"""
    providers = db.query(Provider).filter(
        Provider.org_id == current_user["org_id"]
    ).all()
    
    result = []
    for p in providers:
        # Verificar se org tem credenciais
        has_creds = db.query(ProviderCredential).filter(
            ProviderCredential.org_id == current_user["org_id"],
            ProviderCredential.provider_id == p.id,
            ProviderCredential.is_active == True
        ).first() is not None
        
        result.append(ProviderResponse(
            id=str(p.id),
            name=p.name,
            type=p.type,
            status=p.status,
            has_credentials=has_creds,
            is_configured=has_creds,
        ))
    
    return result

@router.post("/", response_model=ProviderResponse)
def create_provider(
    data: ProviderCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cria um novo provedor para a org"""
    provider = Provider(
        org_id=current_user["org_id"],
        name=data.name,
        type=data.type,
        base_url=data.base_url,
        meta=data.metadata
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    
    return ProviderResponse(
        id=str(provider.id),
        name=provider.name,
        type=provider.type,
        status=provider.status,
        has_credentials=False
    )

@router.post("/credentials")
def set_provider_credentials(
    data: ProviderCredentialCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Configura credenciais do provedor para a org"""
    # Verificar se provider existe
    provider = db.query(Provider).filter(
        Provider.id == data.provider_id,
        Provider.org_id == current_user["org_id"],
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    # Verificar se já existe
    existing = db.query(ProviderCredential).filter(
        ProviderCredential.org_id == current_user["org_id"],
        ProviderCredential.provider_id == data.provider_id
    ).first()
    
    if existing:
        # Atualizar
        existing.credentials_encrypted = encrypt_credentials(data.credentials)
        existing.is_active = True
    else:
        # Criar novo
        credential = ProviderCredential(
            org_id=current_user["org_id"],
            provider_id=data.provider_id,
            credentials_encrypted=encrypt_credentials(data.credentials)
        )
        db.add(credential)
    
    db.commit()
    return {"status": "credentials_saved"}

@router.post("/{provider_id}/health")
async def check_provider_health(
    provider_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Testa conectividade com o provedor"""
    provider = db.query(Provider).filter(
        Provider.id == provider_id,
        Provider.org_id == current_user["org_id"],
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    credential = db.query(ProviderCredential).filter(
        ProviderCredential.org_id == current_user["org_id"],
        ProviderCredential.provider_id == provider_id,
        ProviderCredential.is_active == True
    ).first()
    
    if not credential:
        raise HTTPException(status_code=400, detail="No credentials configured")
    
    try:
        connector = get_connector(
            provider.name,
            decrypt_credentials(credential.credentials_encrypted),
            provider.base_url,
        )
        
        health = await connector.health_check()
        
        return {
            "provider_id": str(provider.id),
            "provider_name": provider.name,
            "healthy": health.get("healthy", False),
            "status_code": health.get("status_code"),
            "latency_ms": health.get("latency_ms"),
            "error": health.get("error")
        }
    
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return {
            "provider_id": str(provider.id),
            "provider_name": provider.name,
            "healthy": False,
            "error": str(e)
        }

@router.delete("/{provider_id}/credentials")
def delete_provider_credentials(
    provider_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove credenciais do provedor"""
    credential = db.query(ProviderCredential).filter(
        ProviderCredential.org_id == current_user["org_id"],
        ProviderCredential.provider_id == provider_id
    ).first()
    
    if not credential:
        raise HTTPException(status_code=404, detail="Credentials not found")
    
    credential.is_active = False
    db.commit()
    
    return {"status": "credentials_removed"}
