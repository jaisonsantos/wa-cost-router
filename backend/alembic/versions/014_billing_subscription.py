from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "014_billing_subscription"
down_revision = "013_integration_health_status"
branch_labels = None
depends_on = None


BILLING_STATUS_ENUM = (
    "active",
    "trialing",
    "past_due",
    "canceled",
    "incomplete",
    "incomplete_expired",
    "unpaid",
)


def upgrade() -> None:
    # 1) Garante que o tipo ENUM exista no banco
    status_enum = postgresql.ENUM(
        *BILLING_STATUS_ENUM,
        name="billingstatusenum",
    )
    status_enum.create(op.get_bind(), checkfirst=True)

    # 2) Tipo a ser usado na coluna (não recria o tipo)
    status_column_enum = postgresql.ENUM(
        *BILLING_STATUS_ENUM,
        name="billingstatusenum",
        create_type=False,
    )

    # 3) Cria a tabela
    op.create_table(
        "billing_subscription",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,  # uma assinatura por organização
        ),
        sa.Column("stripe_customer_id", sa.String(), nullable=False),
        sa.Column("stripe_subscription_id", sa.String()),
        sa.Column(
            "status",
            status_column_enum,
            nullable=False,
            server_default=sa.text("'incomplete'::billingstatusenum"),
        ),
        sa.Column("plan_nickname", sa.String()),
        sa.Column("price_id", sa.String()),
        sa.Column("currency", sa.String()),
        sa.Column("amount_minor", sa.Integer()),
        sa.Column("message_quota", sa.Integer()),
        sa.Column("message_usage", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("latest_invoice_url", sa.String()),
        sa.Column("default_payment_method", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("billing_subscription")

    status_enum = postgresql.ENUM(
        *BILLING_STATUS_ENUM,
        name="billingstatusenum",
    )
    status_enum.drop(op.get_bind(), checkfirst=True)
