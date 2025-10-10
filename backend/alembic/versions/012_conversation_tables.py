"""Add conversation tracking tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "012_conversation_tables"
down_revision = "011_message_multi_channel"
branch_labels = None
depends_on = None


def _create_enum_if_not_exists(enum_type: postgresql.ENUM) -> None:
    enum_name = enum_type.name
    enum_values = ", ".join(f"'{value}'" for value in enum_type.enums)

    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_type WHERE typname = :enum_name
                ) THEN
                    EXECUTE format('CREATE TYPE %I AS ENUM (%s)', :enum_name, :enum_values);
                END IF;
            END
            $$;
            """
        ).bindparams(enum_name=enum_name, enum_values=enum_values)
    )


def upgrade() -> None:
    conversation_status_enum = postgresql.ENUM(
        "open",
        "waiting",
        "closed",
        name="conversationstatusenum",
        create_type=False,
    )
    queue_status_enum = postgresql.ENUM(
        "open",
        "responded",
        "closed",
        name="queuestatusenum",
        create_type=False,
    )

    _create_enum_if_not_exists(conversation_status_enum)
    _create_enum_if_not_exists(queue_status_enum)

    op.create_table(
        "conversation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contact.id", ondelete="SET NULL"),
        ),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("channel_address", sa.String(), nullable=False),
        sa.Column("status", conversation_status_enum, nullable=False, server_default="waiting"),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True)),
        sa.Column("last_outbound_at", sa.DateTime(timezone=True)),
        sa.Column("first_response_at", sa.DateTime(timezone=True)),
        sa.Column("first_response_latency_seconds", sa.Integer()),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_conversation_org_id", "conversation", ["org_id"], unique=False)
    op.create_index("ix_conversation_contact_id", "conversation", ["contact_id"], unique=False)
    op.create_index(
        "ix_conversation_org_channel_status",
        "conversation",
        ["org_id", "channel", "status"],
        unique=False,
    )

    op.create_table(
        "queue_entry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("status", queue_status_enum, nullable=False, server_default="open"),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("first_response_latency_seconds", sa.Integer()),
        sa.Column("total_duration_seconds", sa.Integer()),
        sa.Column("metadata", sa.JSON()),
    )
    op.create_index("ix_queue_entry_org_id", "queue_entry", ["org_id"], unique=False)
    op.create_index(
        "ix_queue_entry_conversation_id",
        "queue_entry",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_queue_entry_org_channel_status",
        "queue_entry",
        ["org_id", "channel", "status"],
        unique=False,
    )

    op.create_table(
        "sla_snapshot",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sla_target_seconds", sa.Integer(), nullable=False),
        sa.Column("conversations_opened", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conversations_closed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_response_avg_seconds", sa.Integer()),
        sa.Column("first_response_within_target", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("backlog_open", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("backlog_closed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("backlog_pending", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("org_id", "channel", "period_start", name="uq_sla_snapshot_period"),
    )
    op.create_index("ix_sla_snapshot_org_id", "sla_snapshot", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sla_snapshot_org_id", table_name="sla_snapshot")
    op.drop_table("sla_snapshot")

    op.drop_index("ix_queue_entry_org_channel_status", table_name="queue_entry")
    op.drop_index("ix_queue_entry_conversation_id", table_name="queue_entry")
    op.drop_index("ix_queue_entry_org_id", table_name="queue_entry")
    op.drop_table("queue_entry")

    op.drop_index("ix_conversation_org_channel_status", table_name="conversation")
    op.drop_index("ix_conversation_contact_id", table_name="conversation")
    op.drop_index("ix_conversation_org_id", table_name="conversation")
    op.drop_table("conversation")

    queue_status_enum = postgresql.ENUM(name="queuestatusenum")
    conversation_status_enum = postgresql.ENUM(name="conversationstatusenum")

    queue_status_enum.drop(op.get_bind(), checkfirst=True)
    conversation_status_enum.drop(op.get_bind(), checkfirst=True)
