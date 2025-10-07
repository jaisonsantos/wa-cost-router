from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import List, Dict, Any
from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.models import MessageEvent, DeliveryAttempt, MessageJob, Provider

router = APIRouter()

class SummaryResponse(BaseModel):
    cost_7d_minor: int
    saved_7d_minor: int
    pct_saved: float

class ProviderMetric(BaseModel):
    provider_id: str
    provider_name: str
    total_sent: int
    success_rate: float
    avg_latency_ms: float
    total_cost_minor: int

class DashboardMetrics(BaseModel):
    total_messages: int
    total_cost_minor: int
    baseline_cost_minor: int
    saved_minor: int
    success_rate: float
    avg_latency_ms: float
    top_countries: List[Dict[str, Any]]
    top_templates: List[Dict[str, Any]]
    alerts: List[Dict[str, Any]]
    recommendations: List[str]

@router.get("/summary", response_model=SummaryResponse)
def get_summary(
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Default to last 7 days
    if not from_date:
        from_dt = datetime.utcnow() - timedelta(days=7)
    else:
        from_dt = datetime.fromisoformat(from_date)
    
    if not to_date:
        to_dt = datetime.utcnow()
    else:
        to_dt = datetime.fromisoformat(to_date)
    
    total_cost = db.query(func.sum(MessageEvent.unit_cost_minor)).filter(
        MessageEvent.org_id == current_user["org_id"],
        MessageEvent.timestamp_provider >= from_dt,
        MessageEvent.timestamp_provider <= to_dt,
        MessageEvent.unit_cost_minor.isnot(None)
    ).scalar() or 0
    
    # Calculate baseline (most expensive provider for each message)
    baseline_cost = db.query(func.sum(MessageEvent.baseline_cost_minor)).filter(
        MessageEvent.org_id == current_user["org_id"],
        MessageEvent.timestamp_provider >= from_dt,
        MessageEvent.timestamp_provider <= to_dt,
        MessageEvent.baseline_cost_minor.isnot(None)
    ).scalar() or 0
    
    # Calculate savings
    saved = max(0, baseline_cost - total_cost)
    pct = 0.0
    if baseline_cost > 0:
        pct = (saved / baseline_cost) * 100
    
    return SummaryResponse(
        cost_7d_minor=total_cost,
        saved_7d_minor=saved,
        pct_saved=pct
    )

@router.get("/dashboard-metrics", response_model=DashboardMetrics)
def get_dashboard_metrics(
    days: int = Query(7, ge=1, le=90),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Métricas completas do dashboard"""
    from_dt = datetime.utcnow() - timedelta(days=days)
    org_id = current_user["org_id"]
    
    # Total de mensagens
    total_messages = db.query(func.count(MessageJob.id)).filter(
        MessageJob.org_id == org_id,
        MessageJob.created_at >= from_dt
    ).scalar() or 0
    
    # Custo total otimizado
    total_cost = db.query(func.sum(MessageEvent.unit_cost_minor)).filter(
        MessageEvent.org_id == org_id,
        MessageEvent.timestamp_provider >= from_dt,
        MessageEvent.unit_cost_minor.isnot(None)
    ).scalar() or 0
    
    # Custo baseline (sem otimização)
    baseline_cost = db.query(func.sum(MessageEvent.baseline_cost_minor)).filter(
        MessageEvent.org_id == org_id,
        MessageEvent.timestamp_provider >= from_dt,
        MessageEvent.baseline_cost_minor.isnot(None)
    ).scalar() or 0
    
    # Taxa de sucesso
    successful = db.query(func.count(DeliveryAttempt.id)).filter(
        DeliveryAttempt.message_job_id.in_(
            db.query(MessageJob.id).filter(MessageJob.org_id == org_id)
        ),
        DeliveryAttempt.timestamp >= from_dt,
        DeliveryAttempt.status == "success"
    ).scalar() or 0
    
    total_attempts = db.query(func.count(DeliveryAttempt.id)).filter(
        DeliveryAttempt.message_job_id.in_(
            db.query(MessageJob.id).filter(MessageJob.org_id == org_id)
        ),
        DeliveryAttempt.timestamp >= from_dt
    ).scalar() or 1
    
    success_rate = (successful / total_attempts) * 100 if total_attempts > 0 else 0
    
    # Latência média
    avg_latency = db.query(func.avg(DeliveryAttempt.latency_ms)).filter(
        DeliveryAttempt.message_job_id.in_(
            db.query(MessageJob.id).filter(MessageJob.org_id == org_id)
        ),
        DeliveryAttempt.timestamp >= from_dt,
        DeliveryAttempt.status == "success",
        DeliveryAttempt.latency_ms.isnot(None)
    ).scalar() or 0
    
    # Top países por custo
    top_countries_data = db.query(
        MessageEvent.country_iso,
        func.sum(MessageEvent.unit_cost_minor).label("total_cost"),
        func.count(MessageEvent.id).label("count")
    ).filter(
        MessageEvent.org_id == org_id,
        MessageEvent.timestamp_provider >= from_dt,
        MessageEvent.country_iso.isnot(None)
    ).group_by(MessageEvent.country_iso).order_by(
        func.sum(MessageEvent.unit_cost_minor).desc()
    ).limit(5).all()
    
    top_countries = [
        {
            "country": row.country_iso,
            "cost_minor": row.total_cost or 0,
            "count": row.count
        }
        for row in top_countries_data
    ]
    
    # Top templates por custo
    top_templates_data = db.query(
        MessageEvent.template_name,
        func.sum(MessageEvent.unit_cost_minor).label("total_cost"),
        func.count(MessageEvent.id).label("count")
    ).filter(
        MessageEvent.org_id == org_id,
        MessageEvent.timestamp_provider >= from_dt,
        MessageEvent.template_name.isnot(None)
    ).group_by(MessageEvent.template_name).order_by(
        func.sum(MessageEvent.unit_cost_minor).desc()
    ).limit(5).all()
    
    top_templates = [
        {
            "template": row.template_name,
            "cost_minor": row.total_cost or 0,
            "count": row.count
        }
        for row in top_templates_data
    ]
    
    # Alertas e recomendações
    alerts = []
    recommendations = []
    
    # Alerta: Taxa de sucesso baixa
    if success_rate < 95:
        alerts.append({
            "type": "warning",
            "message": f"Taxa de sucesso está em {success_rate:.1f}% (ideal: >95%)",
            "action": "Verifique a configuração dos provedores"
        })
    
    # Alerta: Latência alta
    if avg_latency > 3000:
        alerts.append({
            "type": "warning",
            "message": f"Latência média de {avg_latency:.0f}ms (ideal: <2000ms)",
            "action": "Considere adicionar mais provedores"
        })
    
    # Recomendação: Otimização disponível
    saved = max(0, baseline_cost - total_cost)
    if saved > 0:
        recommendations.append(f"Você economizou ${saved/100:.2f} nos últimos {days} dias com otimização de rotas")
    
    # Recomendação: Diversificar provedores
    active_providers = db.query(func.count(func.distinct(DeliveryAttempt.provider_id))).filter(
        DeliveryAttempt.message_job_id.in_(
            db.query(MessageJob.id).filter(MessageJob.org_id == org_id)
        ),
        DeliveryAttempt.timestamp >= from_dt
    ).scalar() or 0
    
    if active_providers < 2:
        recommendations.append("Conecte mais provedores para aumentar resiliência e reduzir custos")
    
    return DashboardMetrics(
        total_messages=total_messages,
        total_cost_minor=total_cost,
        baseline_cost_minor=baseline_cost,
        saved_minor=saved,
        success_rate=success_rate,
        avg_latency_ms=float(avg_latency),
        top_countries=top_countries,
        top_templates=top_templates,
        alerts=alerts,
        recommendations=recommendations
    )

@router.get("/provider-metrics", response_model=List[ProviderMetric])
def get_provider_metrics(
    days: int = Query(7, ge=1, le=90),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Métricas de desempenho por provedor"""
    from_dt = datetime.utcnow() - timedelta(days=days)
    org_id = current_user["org_id"]
    
    # Query combinada para todas as métricas por provedor
    provider_stats = (
        db.query(
            Provider.id,
            Provider.name,
            func.count(DeliveryAttempt.id).label("total_attempts"),
            func.sum(case((DeliveryAttempt.status == "success", 1), else_=0)).label("successful"),
            func.avg(
                case((DeliveryAttempt.status == "success", DeliveryAttempt.latency_ms), else_=None)
            ).label("avg_latency"),
            func.sum(MessageEvent.unit_cost_minor).label("total_cost"),
        )
        .select_from(Provider)
        .outerjoin(
            DeliveryAttempt,
            and_(
                DeliveryAttempt.provider_id == Provider.id,
                DeliveryAttempt.timestamp >= from_dt,
            ),
        )
        .outerjoin(
            MessageJob,
            and_(
                MessageJob.id == DeliveryAttempt.message_job_id,
                MessageJob.org_id == org_id,
            ),
        )
        .outerjoin(
            MessageEvent,
            and_(
                MessageEvent.message_job_id == MessageJob.id,
                MessageEvent.org_id == org_id,
                MessageEvent.timestamp_provider >= from_dt,
            ),
        )
        .filter(Provider.org_id == org_id)
        .group_by(Provider.id, Provider.name)
        .all()
    )
    
    metrics = []
    for stat in provider_stats:
        total_attempts = stat.total_attempts or 0
        successful = stat.successful or 0
        success_rate = (successful / total_attempts * 100) if total_attempts > 0 else 0
        
        metrics.append(ProviderMetric(
            provider_id=str(stat.id),
            provider_name=stat.name,
            total_sent=total_attempts,
            success_rate=success_rate,
            avg_latency_ms=float(stat.avg_latency or 0),
            total_cost_minor=stat.total_cost or 0
        ))
    
    return metrics
