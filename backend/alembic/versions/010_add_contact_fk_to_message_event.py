"""Add contact_id foreign key to message_event"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "010_add_contact_fk_to_message_event"
down_revision = "009_add_contact_segment_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "message_event",
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contact.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_message_event_contact_id",
        "message_event",
        ["contact_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_message_event_contact_id", table_name="message_event")
    op.drop_column("message_event", "contact_id")
