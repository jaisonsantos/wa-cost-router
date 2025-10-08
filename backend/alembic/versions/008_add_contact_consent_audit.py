"""Add contact consent audit table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "008_add_contact_consent_audit"
down_revision = "007_add_contact_domain"
branch_labels = None
depends_on = None


def _ensure_enum(enum_type: postgresql.ENUM) -> None:
    """Create enum type if it does not already exist."""

    enum_name = enum_type.name
    enum_values = ", ".join(f"'{value}'" for value in enum_type.enums)

    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_type WHERE typname = :enum_name
                ) THEN
                    EXECUTE format('CREATE TYPE %I AS ENUM (%s)', :enum_name, :enum_values);
                END IF;
            END
            $$;
            """
        ).bindparams(enum_name=enum_name, enum_values=enum_values)
    )


def upgrade() -> None:
    opt_in_status_enum = postgresql.ENUM(
        "granted",
        "revoked",
        "pending",
        name="optinstatusenum",
        create_type=False,
    )

    _ensure_enum(opt_in_status_enum)

    op.create_table(
        "contact_consent_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contact.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opt_in_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contact_channel_opt_in.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("channel_address", sa.String(), nullable=False),
        sa.Column("status", opt_in_status_enum, nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("agent", sa.String(), nullable=False),
        sa.Column("request_ip", sa.String(length=45), nullable=True),
        sa.Column("evidence_uri", sa.String(), nullable=True),
        sa.Column("proof_hash", sa.String(), nullable=True),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_contact_consent_audit_org_id",
        "contact_consent_audit",
        ["org_id"],
    )
    op.create_index(
        "ix_contact_consent_audit_contact_id",
        "contact_consent_audit",
        ["contact_id"],
    )
    op.create_index(
        "ix_contact_consent_audit_opt_in_id",
        "contact_consent_audit",
        ["opt_in_id"],
    )
    op.create_index(
        "ix_contact_consent_audit_contact_channel",
        "contact_consent_audit",
        ["contact_id", "channel"],
    )
    op.create_index(
        "ix_contact_consent_audit_recorded_at",
        "contact_consent_audit",
        ["recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_contact_consent_audit_recorded_at", table_name="contact_consent_audit")
    op.drop_index("ix_contact_consent_audit_contact_channel", table_name="contact_consent_audit")
    op.drop_index("ix_contact_consent_audit_opt_in_id", table_name="contact_consent_audit")
    op.drop_index("ix_contact_consent_audit_contact_id", table_name="contact_consent_audit")
    op.drop_index("ix_contact_consent_audit_org_id", table_name="contact_consent_audit")
    op.drop_table("contact_consent_audit")
