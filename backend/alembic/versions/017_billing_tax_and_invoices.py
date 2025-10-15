"""Add billing invoice table and tax tracking columns."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "017_billing_tax_and_invoices"
down_revision = "016_billing_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "billing_subscription",
        sa.Column("tax_behavior", sa.String(), nullable=True),
    )
    op.add_column(
        "billing_subscription",
        sa.Column(
            "tax_amount_total_minor",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.create_table(
        "billing_invoice",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stripe_invoice_id", sa.String(), nullable=False, unique=True),
        sa.Column("stripe_customer_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("subtotal_minor", sa.Integer(), nullable=True),
        sa.Column(
            "tax_amount_total_minor",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("total_minor", sa.Integer(), nullable=True),
        sa.Column("tax_behavior", sa.String(), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index("ix_billing_invoice_org_id", "billing_invoice", ["org_id"])
    op.create_index(
        "ix_billing_invoice_stripe_customer_id",
        "billing_invoice",
        ["stripe_customer_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_billing_invoice_stripe_customer_id", table_name="billing_invoice")
    op.drop_index("ix_billing_invoice_org_id", table_name="billing_invoice")
    op.drop_table("billing_invoice")

    op.drop_column("billing_subscription", "tax_amount_total_minor")
    op.drop_column("billing_subscription", "tax_behavior")
