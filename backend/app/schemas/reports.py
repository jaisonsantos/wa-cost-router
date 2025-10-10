from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


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


class ChannelBacklogMetrics(BaseModel):
    open: int
    pending: int
    closed: int


class QueueBacklogMetrics(BaseModel):
    open: int
    responded: int
    closed: int
    total: int


class FirstResponseMetrics(BaseModel):
    average_seconds: Optional[float]
    sample_size: int


class SlaMetrics(BaseModel):
    target_seconds: Optional[float]
    within_target: int
    total_tracked: int
    compliance_rate: Optional[float]


class ChannelMetric(BaseModel):
    channel: str
    conversations_opened: int
    conversations_closed: int
    backlog: ChannelBacklogMetrics
    first_response: FirstResponseMetrics
    sla: SlaMetrics


class QueueMetrics(BaseModel):
    channel: str
    backlog: QueueBacklogMetrics
    first_response: FirstResponseMetrics
    sla: SlaMetrics
