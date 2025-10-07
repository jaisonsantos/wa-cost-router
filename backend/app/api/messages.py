from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.models import (
    MessageJob, DeliveryAttempt, CostRecord, Provider, ProviderCredential,
    JobStatusEnum, AttemptStatusEnum
)
from app.services.routing_engine import RoutingEngine
from app.services.provider_connectors import get_connector
from app.core.security import decrypt_credentials
import logging
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)

class SendMessageRequest(BaseModel):
    idempotency_key: str
    to_number: str
    template_id: str
    template_category: str = "marketing"
    variables: Dict[str, Any] = {}
    country_iso: Optional[str] = None

class SendMessageResponse(BaseModel):
    job_id: str
    status: str
    provider_used: Optional[str] = None
    estimated_cost: Optional[int] = None
    message: str

@router.post("/send", response_model=SendMessageResponse)
async def send_message(
    data: SendMessageRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Envia mensagem via roteamento inteligente
    - Aplica regras
    - Escolhe provedor
    - Tenta com retry e fallback
    - Registra custo e tentativas
    """
    
    # 1. Verificar idempotência
    existing_job = db.query(MessageJob).filter(
        MessageJob.org_id == current_user["org_id"],
        MessageJob.idempotency_key == data.idempotency_key
    ).first()
    
    if existing_job:
        return SendMessageResponse(
            job_id=str(existing_job.id),
            status=existing_job.status.value,
            message="Message already processed (idempotent)"
        )
    
    # 2. Inferir país do número se não fornecido
    country_iso = data.country_iso or _infer_country_from_number(data.to_number)
    
    # 3. Criar job
    job = MessageJob(
        org_id=current_user["org_id"],
        idempotency_key=data.idempotency_key,
        to_number=data.to_number,
        template_id=data.template_id,
        template_category=data.template_category,
        variables=data.variables,
        country_iso=country_iso,
        status=JobStatusEnum.processing
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # 4. Escolher provedor via motor de decisão
    engine = RoutingEngine(db, current_user["org_id"])
    routing_decision = engine.select_provider(
        country_iso=country_iso,
        category=data.template_category,
        template_id=data.template_id
    )
    
    if not routing_decision:
        job.status = JobStatusEnum.failed_final
        db.commit()
        raise HTTPException(status_code=400, detail="No provider available for this route")
    
    # 5. Tentar envio com fallback
    result = await _attempt_delivery_with_fallback(
        db=db,
        job=job,
        routing_decision=routing_decision,
        data=data,
        org_id=current_user["org_id"]
    )
    
    return SendMessageResponse(
        job_id=str(job.id),
        status=result["status"],
        provider_used=result.get("provider_name"),
        estimated_cost=routing_decision["estimated_cost"],
        message=result.get("message", "Message sent successfully")
    )

async def _attempt_delivery_with_fallback(
    db: Session,
    job: MessageJob,
    routing_decision: Dict[str, Any],
    data: SendMessageRequest,
    org_id: str
) -> Dict[str, Any]:
    """Tenta entrega com retry e fallback"""
    
    providers_to_try = [routing_decision["provider_id"]] + routing_decision.get("fallback_chain", [])
    attempt_number = 0
    
    for provider_id in providers_to_try:
        attempt_number += 1
        
        # Obter credenciais
        credential = db.query(ProviderCredential).filter(
            ProviderCredential.org_id == org_id,
            ProviderCredential.provider_id == provider_id,
            ProviderCredential.is_active.is_(True)
        ).first()

        if not credential:
            logger.warning(f"No credentials for provider {provider_id}")
            continue

        provider = db.query(Provider).filter(
            Provider.id == provider_id,
            Provider.org_id == org_id,
        ).first()
        if not provider:
            continue

        try:
            credentials_payload = decrypt_credentials(credential.credentials_encrypted)
        except Exception as exc:
            logger.error(f"Invalid credentials payload for provider {provider_id}: {exc}")
            continue

        # Tentar envio com retries
        for retry in range(3):
            try:
                connector = get_connector(
                    provider.name,
                    credentials_payload,
                    provider.base_url
                )
                
                result = await connector.send_message(
                    to_number=data.to_number,
                    template_id=data.template_id,
                    variables=data.variables
                )
                
                # Gravar tentativa
                attempt = DeliveryAttempt(
                    message_job_id=job.id,
                    provider_id=provider.id,
                    attempt_number=attempt_number,
                    status=AttemptStatusEnum.success if result["success"] else AttemptStatusEnum.failed,
                    error_code=result.get("error_code"),
                    error_message=result.get("error_message"),
                    latency_ms=result.get("latency_ms"),
                    provider_message_id=result.get("provider_message_id"),
                    provider_response=result.get("response")
                )
                db.add(attempt)
                
                if result["success"]:
                    # Sucesso! Gravar custo
                    cost_record = CostRecord(
                        message_job_id=job.id,
                        provider_id=provider.id,
                        price_eur=routing_decision["estimated_cost"],
                        country_iso=job.country_iso,
                        category=job.template_category,
                        price_table_version="v1"  # TODO: pegar versão real da tabela de preços
                    )
                    db.add(cost_record)
                    
                    job.status = JobStatusEnum.delivered if attempt_number == 1 else JobStatusEnum.delivered_with_fallback
                    db.commit()
                    
                    return {
                        "status": job.status.value,
                        "provider_name": provider.name,
                        "message": "Message delivered successfully"
                    }
                
                # Falha, tentar retry se erro recuperável
                if result.get("error_code") in ["429", "timeout"]:
                    await asyncio.sleep(2 ** retry)  # Exponential backoff
                    continue
                else:
                    break  # Erro não recuperável, próximo provider
            
            except Exception as e:
                logger.error(f"Delivery error: {str(e)}")
                attempt = DeliveryAttempt(
                    message_job_id=job.id,
                    provider_id=provider.id,
                    attempt_number=attempt_number,
                    status=AttemptStatusEnum.failed,
                    error_code="EXCEPTION",
                    error_message=str(e)
                )
                db.add(attempt)
                db.commit()
    
    # Todos os providers falharam
    job.status = JobStatusEnum.failed_final
    db.commit()
    
    return {
        "status": job.status.value,
        "message": "All providers failed"
    }

def _infer_country_from_number(number: str) -> str:
    """Inferir país do código do número (simplificado)"""
    country_codes = {
        "+1": "US",
        "+44": "GB",
        "+55": "BR",
        "+351": "PT",
        "+34": "ES",
        "+49": "DE",
        "+33": "FR"
    }
    
    for code, country in country_codes.items():
        if number.startswith(code):
            return country
    
    return "XX"  # Unknown

@router.get("/jobs")
def list_message_jobs(
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lista jobs de mensagens da organização"""
    query = db.query(MessageJob).filter(
        MessageJob.org_id == current_user["org_id"]
    )
    
    if status:
        try:
            status_enum = JobStatusEnum(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        query = query.filter(MessageJob.status == status_enum)

    jobs = query.order_by(MessageJob.created_at.desc()).limit(100).all()

    job_ids = [job.id for job in jobs]
    cost_map: Dict[str, int] = {}
    if job_ids:
        cost_rows = (
            db.query(CostRecord.message_job_id, func.sum(CostRecord.price_eur))
            .filter(CostRecord.message_job_id.in_(job_ids))
            .group_by(CostRecord.message_job_id)
            .all()
        )
        cost_map = {str(job_id): total or 0 for job_id, total in cost_rows}

    return [
        {
            "id": str(job.id),
            "status": job.status.value,
            "to_number": job.to_number,
            "template_id": job.template_id,
            "template_category": job.template_category,
            "country_iso": job.country_iso,
            "created_at": job.created_at.isoformat(),
            "total_cost_minor": cost_map.get(str(job.id)),
        }
        for job in jobs
    ]

@router.get("/jobs/{job_id}")
def get_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Consulta status de um job"""
    job = db.query(MessageJob).filter(
        MessageJob.id == job_id,
        MessageJob.org_id == current_user["org_id"]
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    attempts = (
        db.query(DeliveryAttempt, Provider)
        .join(Provider, DeliveryAttempt.provider_id == Provider.id)
        .filter(DeliveryAttempt.message_job_id == job.id)
        .order_by(DeliveryAttempt.attempt_number.asc())
        .all()
    )

    total_cost = (
        db.query(func.sum(CostRecord.price_eur))
        .filter(CostRecord.message_job_id == job.id)
        .scalar()
    )

    return {
        "id": str(job.id),
        "status": job.status.value,
        "to_number": job.to_number,
        "template_id": job.template_id,
        "template_category": job.template_category,
        "country_iso": job.country_iso,
        "created_at": job.created_at.isoformat(),
        "total_cost_minor": total_cost or 0,
        "attempts": [
            {
                "id": str(a.id),
                "attempt_number": a.attempt_number,
                "status": a.status.value,
                "provider_id": str(a.provider_id),
                "provider_name": provider.name,
                "latency_ms": a.latency_ms,
                "error_code": a.error_code,
                "error_message": a.error_message,
            }
            for a, provider in attempts
        ],
    }
