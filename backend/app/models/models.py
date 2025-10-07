from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    DateTime,
    ForeignKey,
    JSON,
    Enum,
    UniqueConstraint,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import enum
from app.core.database import Base

class RoleEnum(str, enum.Enum):
    owner = "owner"
    member = "member"

class Organization(Base):
    __tablename__ = "organization"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class User(Base):
    __tablename__ = "user"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

class OrganizationUser(Base):
    __tablename__ = "organization_user"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    role = Column(Enum(RoleEnum), nullable=False)
    
    __table_args__ = (UniqueConstraint('org_id', 'user_id', name='_org_user_uc'),)

class WAConnection(Base):
    __tablename__ = "wa_connection"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False)
    business_id = Column(String, nullable=False)
    phone_id = Column(String, nullable=False)
    access_token_enc = Column(String, nullable=False)
    token_expires_at = Column(DateTime(timezone=True))
    webhook_verify_token = Column(String, nullable=False)
    webhook_secret_enc = Column(Text, nullable=False)
    status = Column(String, default="active")

    __table_args__ = (
        UniqueConstraint("org_id", "webhook_verify_token", name="uq_wa_connection_org_token"),
    )

class WATemplate(Base):
    __tablename__ = "wa_template"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    language = Column(String, nullable=False)
    status = Column(String, nullable=False)
    meta = Column("metadata", JSON)

class MessageEvent(Base):
    __tablename__ = "message_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False, index=True)
    message_job_id = Column(UUID(as_uuid=True), ForeignKey("message_job.id"))
    connection_id = Column(UUID(as_uuid=True), ForeignKey("wa_connection.id"))
    provider_event_id = Column(String, unique=True, nullable=False, index=True)
    direction = Column(String, nullable=False)
    template_name = Column(String)
    category = Column(String)
    country_iso = Column(String)
    phone_cc = Column(String)
    timestamp_provider = Column(DateTime(timezone=True), nullable=False, index=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())
    delivery_status = Column(String)
    unit_cost_minor = Column(Integer)
    baseline_cost_minor = Column(Integer)  # Custo sem otimização (mais caro)
    currency = Column(String)
    attributes = Column(JSON)

class RateCard(Base):
    __tablename__ = "rate_card"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("provider.id"), nullable=False, index=True)
    effective_from = Column(DateTime(timezone=True), nullable=False, index=True)
    source = Column(String, nullable=False)
    country_iso = Column(String, nullable=False)
    category = Column(String, nullable=False)
    template_name = Column(String)
    unit_cost_minor = Column(Integer, nullable=False)
    currency = Column(String, nullable=False)
    notes = Column(String)

class RoutingRule(Base):
    __tablename__ = "routing_rule"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    is_enabled = Column(Boolean, default=True)
    conditions_json = Column(JSON, nullable=False)
    actions_json = Column(JSON, nullable=False)
    priority = Column(Integer, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class RoutedAction(Base):
    __tablename__ = "routed_action"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False)
    rule_id = Column(UUID(as_uuid=True), ForeignKey("routing_rule.id"))
    message_event_id = Column(UUID(as_uuid=True), ForeignKey("message_event.id"))
    action = Column(String, nullable=False)
    status = Column(String, nullable=False)
    provider_response = Column(JSON)
    cost_minor = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class EconomySnapshot(Base):
    __tablename__ = "economy_snapshot"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    baseline_cost_minor = Column(Integer, nullable=False)
    optimized_cost_minor = Column(Integer, nullable=False)
    saved_minor = Column(Integer, nullable=False)

class JobStatusEnum(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    delivered = "delivered"
    delivered_with_fallback = "delivered_with_fallback"
    failed = "failed"
    failed_final = "failed_final"

class AttemptStatusEnum(str, enum.Enum):
    success = "success"
    failed = "failed"
    timeout = "timeout"

class Provider(Base):
    __tablename__ = "provider"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    status = Column(String, default="active")
    base_url = Column(String)
    meta = Column("metadata", JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (UniqueConstraint('org_id', 'name', name='_org_provider_name_uc'),)

class ProviderCredential(Base):
    __tablename__ = "provider_credential"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("provider.id"), nullable=False)
    credentials_encrypted = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint('org_id', 'provider_id', name='_org_provider_uc'),)

class MessageJob(Base):
    __tablename__ = "message_job"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False, index=True)
    idempotency_key = Column(String, nullable=False, index=True)
    to_number = Column(String, nullable=False)
    template_id = Column(String, nullable=False)
    template_category = Column(String)
    variables = Column(JSON)
    country_iso = Column(String)
    status = Column(Enum(JobStatusEnum), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (UniqueConstraint('org_id', 'idempotency_key', name='_org_idempotency_uc'),)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempt"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_job_id = Column(UUID(as_uuid=True), ForeignKey("message_job.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("provider.id"), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    status = Column(Enum(AttemptStatusEnum), nullable=False)
    error_code = Column(String)
    error_message = Column(String)
    latency_ms = Column(Integer)
    provider_message_id = Column(String)
    provider_response = Column(JSON)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class CostRecord(Base):
    __tablename__ = "cost_record"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_job_id = Column(UUID(as_uuid=True), ForeignKey("message_job.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("provider.id"), nullable=False)
    price_eur = Column(Integer, nullable=False)
    country_iso = Column(String)
    category = Column(String)
    price_table_version = Column(String)  # Auditoria de qual versão de preço foi usada
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
