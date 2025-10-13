"""Add dry_run flag to routed_action

Revision ID: 015_routed_action_dry_run_flag
Revises: 014_billing_subscription
Create Date: 2025-02-13 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "015_routed_action_dry_run_flag"
down_revision = "014_billing_subscription"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "routed_action",
        sa.Column(
            "dry_run",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("routed_action", "dry_run")
