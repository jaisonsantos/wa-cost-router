"""Add multi-channel recipient fields"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "011_message_multi_channel"
down_revision = "010_message_event_contact_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "message_job",
        sa.Column("channel", sa.String(), server_default="whatsapp", nullable=False),
    )
    op.add_column(
        "message_job",
        sa.Column("channel_address", sa.String(), nullable=True),
    )
    op.add_column(
        "message_job",
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contact.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_message_job_contact_id",
        "message_job",
        ["contact_id"],
        unique=False,
    )

    op.add_column(
        "message_event",
        sa.Column("channel", sa.String(), server_default="whatsapp", nullable=False),
    )
    op.add_column(
        "message_event",
        sa.Column("channel_address", sa.String(), nullable=True),
    )

    op.alter_column("message_job", "channel", server_default=None)
    op.alter_column("message_event", "channel", server_default=None)


def downgrade() -> None:
    op.drop_column("message_event", "channel_address")
    op.drop_column("message_event", "channel")

    op.drop_index("ix_message_job_contact_id", table_name="message_job")
    op.drop_column("message_job", "contact_id")
    op.drop_column("message_job", "channel_address")
    op.drop_column("message_job", "channel")
