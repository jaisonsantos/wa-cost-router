"""add contact segment policy table"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "009_add_contact_segment_policy"
down_revision = "008_add_contact_consent_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_segment_policy",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "segment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contact_segment.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("limits", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("opt_out", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
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

    op.create_index(
        "ix_contact_segment_policy_org_id",
        "contact_segment_policy",
        ["org_id"],
    )
    op.create_index(
        "ix_contact_segment_policy_segment_id",
        "contact_segment_policy",
        ["segment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_contact_segment_policy_segment_id", table_name="contact_segment_policy")
    op.drop_index("ix_contact_segment_policy_org_id", table_name="contact_segment_policy")
    op.drop_table("contact_segment_policy")
