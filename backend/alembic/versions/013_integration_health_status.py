from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "013_integration_health_status"
down_revision = "012_conversation_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_health_status",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("healthy", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status_code", sa.String()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("error", sa.Text()),
        sa.Column("details", sa.JSON()),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("target_type", "target_id", name="uq_integration_health_target"),
    )
    op.create_index(
        "ix_integration_health_org_channel",
        "integration_health_status",
        ["org_id", "channel"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_integration_health_org_channel", table_name="integration_health_status")
    op.drop_table("integration_health_status")
