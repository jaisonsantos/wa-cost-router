"""Billing usage metered tracking."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "016_billing_usage"
down_revision = "015_routed_action_dry_run_flag"
branch_labels = None
depends_on = None


BILLING_USAGE_STATUS = ("pending", "processing", "succeeded", "failed")


def upgrade() -> None:
    op.add_column(
        "billing_subscription",
        sa.Column("stripe_subscription_item_id", sa.String(), nullable=True),
    )

    op.add_column(
        "message_event",
        sa.Column(
            "is_billable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    status_enum = postgresql.ENUM(*BILLING_USAGE_STATUS, name="billingusagewindowstatusenum")
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "billing_usage_window",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(*BILLING_USAGE_STATUS, name="billingusagewindowstatusenum", create_type=False),
            nullable=False,
            server_default=sa.text("'pending'::billingusagewindowstatusenum"),
        ),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "period_start", "period_end", name="uq_billing_usage_window_org_period"),
    )
    op.create_index(
        "ix_billing_usage_window_org_id",
        "billing_usage_window",
        ["org_id"],
    )
    op.create_index(
        "ix_billing_usage_window_next_run_at",
        "billing_usage_window",
        ["next_run_at"],
    )



def downgrade() -> None:
    op.drop_index("ix_billing_usage_window_next_run_at", table_name="billing_usage_window")
    op.drop_index("ix_billing_usage_window_org_id", table_name="billing_usage_window")
    op.drop_table("billing_usage_window")

    status_enum = postgresql.ENUM(*BILLING_USAGE_STATUS, name="billingusagewindowstatusenum")
    status_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_column("message_event", "is_billable")
    op.drop_column("billing_subscription", "stripe_subscription_item_id")
