"""create initial schema

Revision ID: 000_base_schema
Revises: 
Create Date: 2024-01-01 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "000_base_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    role_enum = sa.Enum("owner", "member", name="roleenum")
    job_status_enum = sa.Enum(
        "pending",
        "processing",
        "delivered",
        "delivered_with_fallback",
        "failed",
        "failed_final",
        name="jobstatusenum",
    )
    attempt_status_enum = sa.Enum("success", "failed", "timeout", name="attemptstatusenum")

    role_enum.create(op.get_bind(), checkfirst=True)
    job_status_enum.create(op.get_bind(), checkfirst=True)
    attempt_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "organization",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "user",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    op.create_table(
        "organization_user",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", role_enum, nullable=False),
        sa.UniqueConstraint("org_id", "user_id", name="_org_user_uc"),
    )

    op.create_table(
        "wa_connection",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("business_id", sa.String(), nullable=False),
        sa.Column("phone_id", sa.String(), nullable=False),
        sa.Column("access_token_enc", sa.String(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("webhook_verify_token", sa.String()),
        sa.Column("status", sa.String(), server_default="active"),
    )

    op.create_table(
        "wa_template",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("metadata", sa.JSON()),
    )

    op.create_table(
        "message_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wa_connection.id", ondelete="SET NULL"),
        ),
        sa.Column("provider_event_id", sa.String(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("template_name", sa.String()),
        sa.Column("category", sa.String()),
        sa.Column("country_iso", sa.String()),
        sa.Column("phone_cc", sa.String()),
        sa.Column("timestamp_provider", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("delivery_status", sa.String()),
        sa.Column("unit_cost_minor", sa.Integer()),
        sa.Column("baseline_cost_minor", sa.Integer()),
        sa.Column("currency", sa.String()),
        sa.Column("attributes", sa.JSON()),
        sa.UniqueConstraint("provider_event_id", name="uq_message_event_provider_event_id"),
    )
    op.create_index("ix_message_event_org_id", "message_event", ["org_id"], unique=False)
    op.create_index(
        "ix_message_event_timestamp_provider",
        "message_event",
        ["timestamp_provider"],
        unique=False,
    )

    op.create_table(
        "rate_card",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("country_iso", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("template_name", sa.String()),
        sa.Column("unit_cost_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("notes", sa.String()),
    )
    op.create_index("ix_rate_card_effective_from", "rate_card", ["effective_from"], unique=False)

    op.create_table(
        "routing_rule",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("conditions_json", sa.JSON(), nullable=False),
        sa.Column("actions_json", sa.JSON(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_routing_rule_org_id", "routing_rule", ["org_id"], unique=False)
    op.create_index("ix_routing_rule_priority", "routing_rule", ["priority"], unique=False)

    op.create_table(
        "routed_action",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("routing_rule.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "message_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("message_event.id", ondelete="SET NULL"),
        ),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("provider_response", sa.JSON()),
        sa.Column("cost_minor", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "economy_snapshot",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("baseline_cost_minor", sa.Integer(), nullable=False),
        sa.Column("optimized_cost_minor", sa.Integer(), nullable=False),
        sa.Column("saved_minor", sa.Integer(), nullable=False),
    )

    op.create_table(
        "provider",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("base_url", sa.String()),
        sa.Column("metadata", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "name", name="_org_provider_name_uc"),
    )
    op.create_index("ix_provider_org_id", "provider", ["org_id"], unique=False)

    op.create_table(
        "provider_credential",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provider.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("credentials_encrypted", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "provider_id", name="_org_provider_uc"),
    )

    op.create_table(
        "message_job",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("to_number", sa.String(), nullable=False),
        sa.Column("template_id", sa.String(), nullable=False),
        sa.Column("template_category", sa.String()),
        sa.Column("variables", sa.JSON()),
        sa.Column("country_iso", sa.String()),
        sa.Column("status", job_status_enum, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "idempotency_key", name="_org_idempotency_uc"),
    )
    op.create_index("ix_message_job_org_id", "message_job", ["org_id"], unique=False)
    op.create_index("ix_message_job_idempotency_key", "message_job", ["idempotency_key"], unique=False)

    op.create_table(
        "delivery_attempt",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "message_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("message_job.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provider.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", attempt_status_enum, nullable=False),
        sa.Column("error_code", sa.String()),
        sa.Column("error_message", sa.String()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("provider_message_id", sa.String()),
        sa.Column("provider_response", sa.JSON()),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "cost_record",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "message_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("message_job.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provider.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price_eur", sa.Integer(), nullable=False),
        sa.Column("country_iso", sa.String()),
        sa.Column("category", sa.String()),
        sa.Column("price_table_version", sa.String()),
    )


def downgrade():
    op.drop_table("cost_record")
    op.drop_table("delivery_attempt")
    op.drop_index("ix_message_job_idempotency_key", table_name="message_job")
    op.drop_index("ix_message_job_org_id", table_name="message_job")
    op.drop_table("message_job")
    op.drop_table("provider_credential")
    op.drop_index("ix_provider_org_id", table_name="provider")
    op.drop_table("provider")
    op.drop_table("economy_snapshot")
    op.drop_table("routed_action")
    op.drop_index("ix_routing_rule_priority", table_name="routing_rule")
    op.drop_index("ix_routing_rule_org_id", table_name="routing_rule")
    op.drop_table("routing_rule")
    op.drop_index("ix_rate_card_effective_from", table_name="rate_card")
    op.drop_table("rate_card")
    op.drop_index("ix_message_event_timestamp_provider", table_name="message_event")
    op.drop_index("ix_message_event_org_id", table_name="message_event")
    op.drop_table("message_event")
    op.drop_table("wa_template")
    op.drop_table("wa_connection")
    op.drop_table("organization_user")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")
    op.drop_table("organization")

    attempt_status_enum = sa.Enum("success", "failed", "timeout", name="attemptstatusenum")
    job_status_enum = sa.Enum(
        "pending",
        "processing",
        "delivered",
        "delivered_with_fallback",
        "failed",
        "failed_final",
        name="jobstatusenum",
    )
    role_enum = sa.Enum("owner", "member", name="roleenum")

    attempt_status_enum.drop(op.get_bind(), checkfirst=True)
    job_status_enum.drop(op.get_bind(), checkfirst=True)
    role_enum.drop(op.get_bind(), checkfirst=True)
