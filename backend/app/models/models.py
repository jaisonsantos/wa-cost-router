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
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
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

    contacts = relationship("Contact", back_populates="organization")
    contact_segments = relationship("ContactSegment", back_populates="organization")
    segment_policies = relationship("ContactSegmentPolicy", back_populates="organization")

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
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_job_id = Column(UUID(as_uuid=True), ForeignKey("message_job.id"))
    connection_id = Column(UUID(as_uuid=True), ForeignKey("wa_connection.id"))
    channel = Column(String, nullable=False, default="whatsapp")
    channel_address = Column(String)
    contact_id = Column(
        UUID(as_uuid=True), ForeignKey("contact.id", ondelete="SET NULL"), nullable=True, index=True
    )
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


class ContactStatusEnum(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    archived = "archived"


class OptInStatusEnum(str, enum.Enum):
    granted = "granted"
    revoked = "revoked"
    pending = "pending"


class OptInRequestStatusEnum(str, enum.Enum):
    pending = "pending"
    sending = "sending"
    sent = "sent"
    confirmed = "confirmed"
    failed = "failed"
    cancelled = "cancelled"


class ContactImportStatusEnum(str, enum.Enum):
    pending = "pending"
    validating = "validating"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ConversationStatusEnum(str, enum.Enum):
    open = "open"
    waiting = "waiting"
    closed = "closed"


class QueueStatusEnum(str, enum.Enum):
    open = "open"
    responded = "responded"
    closed = "closed"


class Conversation(Base):
    __tablename__ = "conversation"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("contact.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel = Column(String, nullable=False)
    channel_address = Column(String, nullable=False)
    status = Column(
        Enum(ConversationStatusEnum),
        nullable=False,
        default=ConversationStatusEnum.waiting,
    )
    opened_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_inbound_at = Column(DateTime(timezone=True))
    last_outbound_at = Column(DateTime(timezone=True))
    first_response_at = Column(DateTime(timezone=True))
    first_response_latency_seconds = Column(Integer)
    closed_at = Column(DateTime(timezone=True))
    meta = Column("metadata", JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_conversation_org_channel_status", "org_id", "channel", "status"),
    )

    queue_entries = relationship(
        "QueueEntry",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class QueueEntry(Base):
    __tablename__ = "queue_entry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel = Column(String, nullable=False)
    status = Column(Enum(QueueStatusEnum), nullable=False, default=QueueStatusEnum.open)
    opened_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    responded_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))
    first_response_latency_seconds = Column(Integer)
    total_duration_seconds = Column(Integer)
    meta = Column("metadata", JSON)

    __table_args__ = (
        Index("ix_queue_entry_org_channel_status", "org_id", "channel", "status"),
    )

    conversation = relationship("Conversation", back_populates="queue_entries")


class SlaSnapshot(Base):
    __tablename__ = "sla_snapshot"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel = Column(String, nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    sla_target_seconds = Column(Integer, nullable=False)
    conversations_opened = Column(Integer, nullable=False, default=0)
    conversations_closed = Column(Integer, nullable=False, default=0)
    first_response_avg_seconds = Column(Integer)
    first_response_within_target = Column(Integer, nullable=False, default=0)
    backlog_open = Column(Integer, nullable=False, default=0)
    backlog_closed = Column(Integer, nullable=False, default=0)
    backlog_pending = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "channel", "period_start", name="uq_sla_snapshot_period"),
    )


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
    channel = Column(String, nullable=False, default="whatsapp")
    channel_address = Column(String)
    contact_id = Column(
        UUID(as_uuid=True), ForeignKey("contact.id", ondelete="SET NULL"), nullable=True, index=True
    )
    template_id = Column(String, nullable=False)
    template_category = Column(String)
    variables = Column(JSON)
    country_iso = Column(String)
    status = Column(Enum(JobStatusEnum), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint('org_id', 'idempotency_key', name='_org_idempotency_uc'),)


class Contact(Base):
    __tablename__ = "contact"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False, index=True)
    external_id = Column(String, index=True)
    full_name = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, index=True)
    phone = Column(String, index=True)
    status = Column(Enum(ContactStatusEnum), nullable=False, default=ContactStatusEnum.active)
    attributes = Column(JSON)
    source = Column(String, nullable=False, default="manual")
    source_metadata = Column(JSON)
    proof_hash = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "external_id", name="uq_contact_org_external_id"),
    )

    organization = relationship("Organization", back_populates="contacts")
    channel_opt_ins = relationship(
        "ContactChannelOptIn",
        back_populates="contact",
        cascade="all, delete-orphan",
    )
    segment_memberships = relationship(
        "ContactSegmentMembership",
        back_populates="contact",
        cascade="all, delete-orphan",
    )
    consent_audits = relationship(
        "ContactConsentAudit",
        back_populates="contact",
        cascade="all, delete-orphan",
    )
    segments = relationship(
        "ContactSegment",
        secondary="contact_segment_membership",
        back_populates="contacts",
        viewonly=True,
    )


class ContactChannelOptIn(Base):
    __tablename__ = "contact_channel_opt_in"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id = Column(
        UUID(as_uuid=True), ForeignKey("contact.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel = Column(String, nullable=False)
    channel_address = Column(String, nullable=False)
    status = Column(Enum(OptInStatusEnum), nullable=False, default=OptInStatusEnum.granted)
    version = Column(Integer, nullable=False, default=1)
    legal_basis = Column(String)
    captured_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source = Column(String, nullable=False, default="manual")
    source_metadata = Column(JSON)
    evidence_uri = Column(String)
    proof_hash = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "contact_id",
            "channel",
            "channel_address",
            "version",
            name="uq_contact_opt_in_version",
        ),
        Index(
            "ix_contact_channel_opt_in_channel_address",
            func.lower(channel_address),
        ),
    )

    organization = relationship("Organization")
    contact = relationship("Contact", back_populates="channel_opt_ins")
    audit_entries = relationship(
        "ContactConsentAudit",
        back_populates="opt_in",
    )


class ContactConsentAudit(Base):
    __tablename__ = "contact_consent_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("contact.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    opt_in_id = Column(
        UUID(as_uuid=True),
        ForeignKey("contact_channel_opt_in.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel = Column(String, nullable=False)
    channel_address = Column(String, nullable=False)
    status = Column(Enum(OptInStatusEnum), nullable=False)
    source = Column(String, nullable=False)
    agent = Column(String, nullable=False)
    request_ip = Column(String(45))
    evidence_uri = Column(String)
    proof_hash = Column(String)
    context = Column(JSON)
    recorded_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_contact_consent_audit_contact_channel",
            "contact_id",
            "channel",
        ),
        Index(
            "ix_contact_consent_audit_recorded_at",
            "recorded_at",
        ),
    )

    contact = relationship("Contact", back_populates="consent_audits")
    opt_in = relationship("ContactChannelOptIn", back_populates="audit_entries")


class ContactOptInRequest(Base):
    __tablename__ = "contact_opt_in_request"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("contact.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    opt_in_id = Column(
        UUID(as_uuid=True),
        ForeignKey("contact_channel_opt_in.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requested_channel = Column(String, nullable=False)
    requested_address = Column(String, nullable=False)
    delivery_channel = Column(String, nullable=False)
    delivery_address = Column(String, nullable=False)
    template_id = Column(String, nullable=False)
    template_variables = Column(JSON, nullable=False, default=dict)
    status = Column(Enum(OptInRequestStatusEnum), nullable=False, default=OptInRequestStatusEnum.pending)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    last_attempt_at = Column(DateTime(timezone=True))
    next_attempt_at = Column(DateTime(timezone=True))
    confirmed_at = Column(DateTime(timezone=True))
    last_error = Column(String)
    external_message_id = Column(String)
    delivery_metadata = Column(JSON)
    confirmation_payload = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index(
            "ix_contact_opt_in_request_contact_channel",
            "contact_id",
            "requested_channel",
        ),
        Index(
            "ix_contact_opt_in_request_next_attempt",
            "status",
            "next_attempt_at",
        ),
    )

    contact = relationship("Contact")
    opt_in = relationship("ContactChannelOptIn")


class ContactSegment(Base):
    __tablename__ = "contact_segment"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    criteria = Column(JSON)
    source = Column(String, nullable=False, default="manual")
    source_metadata = Column(JSON)
    proof_hash = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "slug", name="uq_contact_segment_org_slug"),
    )

    organization = relationship("Organization", back_populates="contact_segments")
    memberships = relationship(
        "ContactSegmentMembership",
        back_populates="segment",
        cascade="all, delete-orphan",
    )
    policy = relationship(
        "ContactSegmentPolicy",
        back_populates="segment",
        cascade="all, delete-orphan",
        uselist=False,
    )
    contacts = relationship(
        "Contact",
        secondary="contact_segment_membership",
        back_populates="segments",
        viewonly=True,
    )


class ContactSegmentPolicy(Base):
    __tablename__ = "contact_segment_policy"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    segment_id = Column(
        UUID(as_uuid=True), ForeignKey("contact_segment.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    limits = Column(JSON, nullable=False, default=dict)
    opt_out = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="segment_policies")
    segment = relationship("ContactSegment", back_populates="policy")


class ContactSegmentMembership(Base):
    __tablename__ = "contact_segment_membership"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id = Column(
        UUID(as_uuid=True), ForeignKey("contact.id", ondelete="CASCADE"), nullable=False, index=True
    )
    segment_id = Column(
        UUID(as_uuid=True), ForeignKey("contact_segment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    membership_origin = Column(String, nullable=False)
    valid_from = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    valid_to = Column(DateTime(timezone=True))
    source = Column(String, nullable=False, default="manual")
    source_metadata = Column(JSON)
    proof_hash = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "contact_id",
            "segment_id",
            "valid_from",
            name="uq_contact_segment_membership_version",
        ),
    )

    organization = relationship("Organization")
    contact = relationship("Contact", back_populates="segment_memberships")
    segment = relationship("ContactSegment", back_populates="memberships")


class ContactImportJob(Base):
    __tablename__ = "contact_import_job"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by = Column(String, nullable=False)
    input_uri = Column(String)
    status = Column(Enum(ContactImportStatusEnum), nullable=False, default=ContactImportStatusEnum.pending)
    total_rows = Column(Integer, nullable=False, default=0)
    processed_rows = Column(Integer, nullable=False, default=0)
    error_rows = Column(Integer, nullable=False, default=0)
    error_report_uri = Column(String)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    source = Column(String, nullable=False, default="manual")
    source_metadata = Column(JSON)
    proof_hash = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_contact_import_job_org_status", "org_id", "status"),
    )

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
