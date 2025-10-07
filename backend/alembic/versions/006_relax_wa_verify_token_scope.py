"""Scope WA verify token uniqueness to org"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "006_relax_wa_verify_token_scope"
down_revision = "005_link_rate_cards_to_providers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_wa_connection_webhook_verify_token",
        "wa_connection",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_wa_connection_org_token",
        "wa_connection",
        ["org_id", "webhook_verify_token"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_wa_connection_org_token", "wa_connection", type_="unique")
    op.create_unique_constraint(
        "uq_wa_connection_webhook_verify_token",
        "wa_connection",
        ["webhook_verify_token"],
    )
