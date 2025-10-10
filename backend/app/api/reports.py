from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.models import (
    DeliveryAttempt,
    MessageEvent,
    MessageJob,
    Provider,
    QueueEntry,
    QueueStatusEnum,
    SlaSnapshot,
)
from app.schemas.reports import (
    ChannelMetric,
    DashboardMetrics,
    FirstResponseMetrics,
    ProviderMetric,
    QueueMetrics,
    SlaMetrics,
    SummaryResponse,
)

router = APIRouter()


def _resolve_interval(
    from_str: Optional[str],
    to_str: Optional[str],
    *,
    default_days: int = 7,
) -> Tuple[datetime, datetime]:
    if to_str:
        to_dt = datetime.fromisoformat(to_str)
    else:
        to_dt = datetime.utcnow()

    if from_str:
        from_dt = datetime.fromisoformat(from_str)
    else:
        from_dt = to_dt - timedelta(days=default_days)

    if from_dt > to_dt:
        raise ValueError("from must be earlier than to")

    return from_dt, to_dt


def _load_sla_metrics(
    db: Session,
    org_id: str,
    from_dt: datetime,
    to_dt: datetime,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, int]]]:
    filters = [
        SlaSnapshot.org_id == org_id,
        SlaSnapshot.period_start >= from_dt,
        SlaSnapshot.period_end <= to_dt,
    ]

    aggregated_subquery = (
        db.query(
            SlaSnapshot.channel.label("channel"),
            func.sum(SlaSnapshot.conversations_opened).label("conversations_opened"),
            func.sum(SlaSnapshot.conversations_closed).label("conversations_closed"),
            func.sum(SlaSnapshot.first_response_within_target).label(
                "first_response_within_target"
            ),
            func.sum(
                case(
                    (
                        SlaSnapshot.first_response_avg_seconds.isnot(None),
                        SlaSnapshot.first_response_avg_seconds
                        * SlaSnapshot.conversations_closed,
                    ),
                    else_=0,
                )
            ).label("first_response_total_seconds"),
            func.sum(
                case(
                    (
                        SlaSnapshot.first_response_avg_seconds.isnot(None),
                        SlaSnapshot.conversations_closed,
                    ),
                    else_=0,
                )
            ).label("first_response_sample_size"),
            func.sum(
                SlaSnapshot.sla_target_seconds * SlaSnapshot.conversations_closed
            ).label("sla_target_weighted"),
        )
        .filter(*filters)
        .group_by(SlaSnapshot.channel)
        .subquery()
    )

    aggregated_rows = db.query(aggregated_subquery).all()

    latest_snapshot_subquery = (
        db.query(
            SlaSnapshot.channel.label("channel"),
            func.max(SlaSnapshot.period_end).label("max_period_end"),
        )
        .filter(*filters)
        .group_by(SlaSnapshot.channel)
        .subquery()
    )

    backlog_rows = (
        db.query(
            SlaSnapshot.channel,
            SlaSnapshot.backlog_open,
            SlaSnapshot.backlog_pending,
            SlaSnapshot.backlog_closed,
        )
        .join(
            latest_snapshot_subquery,
            and_(
                SlaSnapshot.channel == latest_snapshot_subquery.c.channel,
                SlaSnapshot.period_end == latest_snapshot_subquery.c.max_period_end,
            ),
        )
        .all()
    )

    backlog_map: Dict[str, Dict[str, int]] = {
        row.channel: {
            "open": int(row.backlog_open or 0),
            "pending": int(row.backlog_pending or 0),
            "closed": int(row.backlog_closed or 0),
        }
        for row in backlog_rows
    }

    sla_map: Dict[str, Dict[str, float]] = {}
    for row in aggregated_rows:
        channel = row.channel
        conversations_opened = int(row.conversations_opened or 0)
        conversations_closed = int(row.conversations_closed or 0)
        within_target = int(row.first_response_within_target or 0)
        sample_size = int(row.first_response_sample_size or 0)
        total_seconds = float(row.first_response_total_seconds or 0)
        target_weighted = float(row.sla_target_weighted or 0)

        avg_seconds = (
            total_seconds / sample_size if sample_size > 0 else None
        )
        target_seconds = (
            target_weighted / conversations_closed
            if conversations_closed > 0
            else None
        )
        compliance_rate = (
            (within_target / conversations_closed) * 100
            if conversations_closed > 0
            else None
        )

        sla_map[channel] = {
            "conversations_opened": conversations_opened,
            "conversations_closed": conversations_closed,
            "first_response_within_target": within_target,
            "first_response_avg_seconds": avg_seconds,
            "first_response_sample_size": sample_size,
            "sla_target_seconds": target_seconds,
            "sla_compliance_rate": compliance_rate,
        }

    return sla_map, backlog_map

@router.get("/summary", response_model=SummaryResponse)
def get_summary(
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        from_dt, to_dt = _resolve_interval(from_date, to_date)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    org_id = current_user["org_id"]

    total_cost = db.query(func.sum(MessageEvent.unit_cost_minor)).filter(
        MessageEvent.org_id == org_id,
        MessageEvent.timestamp_provider >= from_dt,
        MessageEvent.timestamp_provider <= to_dt,
        MessageEvent.unit_cost_minor.isnot(None)
    ).scalar() or 0

    # Calculate baseline (most expensive provider for each message)
    baseline_cost = db.query(func.sum(MessageEvent.baseline_cost_minor)).filter(
        MessageEvent.org_id == org_id,
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


@router.get("/channel-metrics", response_model=List[ChannelMetric])
def get_channel_metrics(
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        from_dt, to_dt = _resolve_interval(from_date, to_date)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    org_id = current_user["org_id"]
    sla_map, backlog_map = _load_sla_metrics(db, org_id, from_dt, to_dt)

    metrics: List[ChannelMetric] = []
    for channel, sla_data in sla_map.items():
        backlog_data = backlog_map.get(
            channel,
            {"open": 0, "pending": 0, "closed": 0},
        )

        metrics.append(
            ChannelMetric(
                channel=channel,
                conversations_opened=int(sla_data["conversations_opened"]),
                conversations_closed=int(sla_data["conversations_closed"]),
                backlog=backlog_data,
                first_response=FirstResponseMetrics(
                    average_seconds=sla_data["first_response_avg_seconds"],
                    sample_size=int(sla_data["first_response_sample_size"]),
                ),
                sla=SlaMetrics(
                    target_seconds=sla_data["sla_target_seconds"],
                    within_target=int(sla_data["first_response_within_target"]),
                    total_tracked=int(sla_data["conversations_closed"]),
                    compliance_rate=sla_data["sla_compliance_rate"],
                ),
            )
        )

    metrics.sort(key=lambda metric: metric.channel)
    return metrics


@router.get("/queues", response_model=List[QueueMetrics])
def get_queue_metrics(
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        from_dt, to_dt = _resolve_interval(from_date, to_date)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    org_id = current_user["org_id"]
    sla_map, backlog_map = _load_sla_metrics(db, org_id, from_dt, to_dt)

    queue_rows = (
        db.query(
            QueueEntry.channel.label("channel"),
            func.sum(
                case((QueueEntry.status == QueueStatusEnum.open, 1), else_=0)
            ).label("open"),
            func.sum(
                case((QueueEntry.status == QueueStatusEnum.responded, 1), else_=0)
            ).label("responded"),
            func.sum(
                case((QueueEntry.status == QueueStatusEnum.closed, 1), else_=0)
            ).label("closed"),
            func.sum(
                case(
                    (
                        QueueEntry.first_response_latency_seconds.isnot(None),
                        QueueEntry.first_response_latency_seconds,
                    ),
                    else_=0,
                )
            ).label("first_response_total"),
            func.sum(
                case(
                    (
                        QueueEntry.first_response_latency_seconds.isnot(None),
                        1,
                    ),
                    else_=0,
                )
            ).label("first_response_count"),
        )
        .filter(
            QueueEntry.org_id == org_id,
            QueueEntry.opened_at >= from_dt,
            QueueEntry.opened_at <= to_dt,
        )
        .group_by(QueueEntry.channel)
        .all()
    )

    metrics_map: Dict[str, QueueMetrics] = {}

    for row in queue_rows:
        channel = row.channel
        open_count = int(row.open or 0)
        responded_count = int(row.responded or 0)
        closed_count = int(row.closed or 0)
        total_count = open_count + responded_count + closed_count
        first_response_count = int(row.first_response_count or 0)
        first_response_total = float(row.first_response_total or 0)
        avg_first_response = (
            first_response_total / first_response_count
            if first_response_count > 0
            else None
        )

        sla_data = sla_map.get(channel, {})

        metrics_map[channel] = QueueMetrics(
            channel=channel,
            backlog={
                "open": open_count,
                "responded": responded_count,
                "closed": closed_count,
                "total": total_count,
            },
            first_response=FirstResponseMetrics(
                average_seconds=avg_first_response,
                sample_size=first_response_count,
            ),
            sla=SlaMetrics(
                target_seconds=sla_data.get("sla_target_seconds"),
                within_target=int(sla_data.get("first_response_within_target", 0)),
                total_tracked=int(sla_data.get("conversations_closed", 0)),
                compliance_rate=sla_data.get("sla_compliance_rate"),
            ),
        )

    for channel, sla_data in sla_map.items():
        if channel in metrics_map:
            continue

        backlog_data = backlog_map.get(
            channel,
            {"open": 0, "pending": 0, "closed": 0},
        )

        responded_fallback = backlog_data.get("pending", 0)
        total_fallback = (
            backlog_data.get("open", 0)
            + responded_fallback
            + backlog_data.get("closed", 0)
        )

        metrics_map[channel] = QueueMetrics(
            channel=channel,
            backlog={
                "open": backlog_data.get("open", 0),
                "responded": responded_fallback,
                "closed": backlog_data.get("closed", 0),
                "total": total_fallback,
            },
            first_response=FirstResponseMetrics(
                average_seconds=sla_data["first_response_avg_seconds"],
                sample_size=int(sla_data["first_response_sample_size"]),
            ),
            sla=SlaMetrics(
                target_seconds=sla_data["sla_target_seconds"],
                within_target=int(sla_data["first_response_within_target"]),
                total_tracked=int(sla_data["conversations_closed"]),
                compliance_rate=sla_data["sla_compliance_rate"],
            ),
        )

    metrics_list = list(metrics_map.values())
    metrics_list.sort(key=lambda metric: metric.channel)
    return metrics_list
