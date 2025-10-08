from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Dict, Any, Optional, Iterable
from uuid import UUID
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
    try:
        routing_decision = engine.select_provider(
            country_iso=country_iso,
            category=data.template_category,
            template_id=data.template_id,
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception(
            "Routing engine failure for job %s in org %s: %s",
            job.id,
            current_user["org_id"],
            exc,
        )
        job.status = JobStatusEnum.failed_final
        db.commit()
        return SendMessageResponse(
            job_id=str(job.id),
            status=job.status.value,
            provider_used=None,
            estimated_cost=None,
            message="Routing engine error",
        )
    
    if not routing_decision:
        job.status = JobStatusEnum.failed_final
        db.commit()
        raise HTTPException(status_code=400, detail="No provider available for this route")
    
    # 5. Tentar envio com fallback
    estimated_cost_minor = _normalize_estimated_cost(
        routing_decision.get("estimated_cost")
    )

    try:
        result = await _attempt_delivery_with_fallback(
            db=db,
            job=job,
            routing_decision=routing_decision,
            data=data,
            org_id=current_user["org_id"],
            estimated_cost_minor=estimated_cost_minor,
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception(
            "Unexpected delivery failure for job %s via provider %s: %s",
            job.id,
            routing_decision.get("provider_id") if routing_decision else None,
            exc,
        )
        job.status = JobStatusEnum.failed_final
        db.commit()
        result = {
            "status": job.status.value,
            "provider_name": None,
            "message": "Delivery orchestration error",
        }
    
    return SendMessageResponse(
        job_id=str(job.id),
        status=result["status"],
        provider_used=result.get("provider_name"),
        estimated_cost=estimated_cost_minor,
        message=result.get("message", "Message sent successfully")
    )

async def _attempt_delivery_with_fallback(
    db: Session,
    job: MessageJob,
    routing_decision: Dict[str, Any],
    data: SendMessageRequest,
    org_id: str,
    estimated_cost_minor: int,
) -> Dict[str, Any]:
    """Tenta entrega com retry e fallback"""

    org_uuid = _coerce_uuid(org_id)
    if org_uuid is None:
        logger.error("Invalid organization identifier %r for job %s", org_id, job.id)
        job.status = JobStatusEnum.failed_final
        db.commit()
        return {
            "status": job.status.value,
            "message": "Invalid organization context",
        }

    raw_providers = []

    primary_identifier = routing_decision.get("provider_id")
    if primary_identifier is not None:
        raw_providers.append(primary_identifier)

    fallback_chain = routing_decision.get("fallback_chain")
    if fallback_chain in (None, ""):
        fallback_candidates: Iterable[Any] = []
    elif isinstance(fallback_chain, Iterable) and not isinstance(fallback_chain, (str, bytes)):
        fallback_candidates = fallback_chain
    else:
        logger.warning(
            "Invalid fallback chain %r for job %s; ignoring",
            fallback_chain,
            job.id,
        )
        fallback_candidates = []

    raw_providers.extend(list(fallback_candidates))

    providers_to_try = []
    for raw_identifier in raw_providers:
        provider_uuid = _coerce_uuid(raw_identifier)
        if provider_uuid is None:
            logger.warning("Skipping invalid provider identifier %r", raw_identifier)
            continue
        providers_to_try.append(provider_uuid)

    attempt_number = 0

    for provider_id in providers_to_try:
        attempt_number += 1
        
        # Obter credenciais
        credential = db.query(ProviderCredential).filter(
            ProviderCredential.org_id == org_uuid,
            ProviderCredential.provider_id == provider_id,
            ProviderCredential.is_active.is_(True)
        ).first()

        if not credential:
            logger.warning(f"No credentials for provider {provider_id}")
            continue

        provider = db.query(Provider).filter(
            Provider.id == provider_id,
            Provider.org_id == org_uuid,
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
                        price_eur=estimated_cost_minor,
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


def _normalize_estimated_cost(value: Any) -> int:
    """Coerce arbitrary estimated cost values into a non-negative integer."""

    if value is None:
        return 0

    try:
        cost = int(value)
    except (TypeError, ValueError):
        logger.warning("Invalid estimated cost %r; defaulting to 0", value)
        return 0

    return max(cost, 0)


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


def _coerce_uuid(value: Any) -> Optional[UUID]:
    """Safely convert arbitrary identifiers into UUID objects."""

    if isinstance(value, UUID):
        return value

    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None

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
