"""Link rate cards to providers"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "005_link_rate_cards_to_providers"
down_revision = "004_add_wa_webhook_secret"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rate_card",
        sa.Column(
            "provider_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index("ix_rate_card_provider_id", "rate_card", ["provider_id"])
    op.create_foreign_key(
        "fk_rate_card_provider_id",
        "rate_card",
        "provider",
        ["provider_id"],
        ["id"],
        ondelete="CASCADE",
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE rate_card AS rc
            SET provider_id = provider.id
            FROM provider
            WHERE rc.provider_id IS NULL
              AND lower(rc.source) = lower(provider.name)
            """
        )
    )

    connection.execute(
        sa.text("DELETE FROM rate_card WHERE provider_id IS NULL")
    )

    op.alter_column("rate_card", "provider_id", nullable=False)


def downgrade() -> None:
    op.drop_constraint("fk_rate_card_provider_id", "rate_card", type_="foreignkey")
    op.drop_index("ix_rate_card_provider_id", table_name="rate_card")
    op.drop_column("rate_card", "provider_id")
