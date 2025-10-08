"""add contact catalog and opt-in tables"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "007_add_contact_domain"
down_revision = "006_relax_wa_verify_token_scope"
branch_labels = None
depends_on = None


def _create_enum_if_not_exists(enum_type: postgresql.ENUM) -> None:
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
    contact_status_enum = postgresql.ENUM(
        "active",
        "inactive",
        "archived",
        name="contactstatusenum",
        create_type=False,
    )
    opt_in_status_enum = postgresql.ENUM(
        "granted",
        "revoked",
        "pending",
        name="optinstatusenum",
        create_type=False,
    )
    import_status_enum = postgresql.ENUM(
        "pending",
        "validating",
        "processing",
        "completed",
        "failed",
        name="contactimportstatusenum",
        create_type=False,
    )

    _create_enum_if_not_exists(contact_status_enum)
    _create_enum_if_not_exists(opt_in_status_enum)
    _create_enum_if_not_exists(import_status_enum)

    op.create_table(
        "contact",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column(
            "status",
            contact_status_enum,
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("attributes", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("source_metadata", sa.JSON(), nullable=True),
        sa.Column("proof_hash", sa.String(), nullable=True),
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
        sa.UniqueConstraint("org_id", "external_id", name="uq_contact_org_external_id"),
    )

    op.create_table(
        "contact_channel_opt_in",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
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
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("channel_address", sa.String(), nullable=False),
        sa.Column(
            "status",
            opt_in_status_enum,
            nullable=False,
            server_default=sa.text("'granted'"),
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("legal_basis", sa.String(), nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("source", sa.String(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("source_metadata", sa.JSON(), nullable=True),
        sa.Column("evidence_uri", sa.String(), nullable=True),
        sa.Column("proof_hash", sa.String(), nullable=True),
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
        sa.UniqueConstraint(
            "contact_id",
            "channel",
            "channel_address",
            "version",
            name="uq_contact_opt_in_version",
        ),
    )

    op.create_table(
        "contact_segment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("criteria", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("source_metadata", sa.JSON(), nullable=True),
        sa.Column("proof_hash", sa.String(), nullable=True),
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
        sa.UniqueConstraint("org_id", "slug", name="uq_contact_segment_org_slug"),
    )

    op.create_table(
        "contact_segment_membership",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
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
            "segment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contact_segment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("membership_origin", sa.String(), nullable=False),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("source_metadata", sa.JSON(), nullable=True),
        sa.Column("proof_hash", sa.String(), nullable=True),
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
        sa.UniqueConstraint(
            "contact_id",
            "segment_id",
            "valid_from",
            name="uq_contact_segment_membership_version",
        ),
    )

    op.create_table(
        "contact_import_job",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("input_uri", sa.String(), nullable=True),
        sa.Column(
            "status",
            import_status_enum,
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("processed_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_report_uri", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("source_metadata", sa.JSON(), nullable=True),
        sa.Column("proof_hash", sa.String(), nullable=True),
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

    op.create_index("ix_contact_org_id", "contact", ["org_id"])
    op.create_index("ix_contact_external_id", "contact", ["external_id"])
    op.create_index("ix_contact_email", "contact", ["email"])
    op.create_index("ix_contact_phone", "contact", ["phone"])

    op.create_index("ix_contact_channel_opt_in_org_id", "contact_channel_opt_in", ["org_id"])
    op.create_index(
        "ix_contact_channel_opt_in_contact_id",
        "contact_channel_opt_in",
        ["contact_id"],
    )
    op.create_index(
        "ix_contact_channel_opt_in_channel_address",
        "contact_channel_opt_in",
        ["channel_address"],
    )

    op.create_index("ix_contact_segment_org_id", "contact_segment", ["org_id"])

    op.create_index(
        "ix_contact_segment_membership_org_id",
        "contact_segment_membership",
        ["org_id"],
    )
    op.create_index(
        "ix_contact_segment_membership_contact_id",
        "contact_segment_membership",
        ["contact_id"],
    )
    op.create_index(
        "ix_contact_segment_membership_segment_id",
        "contact_segment_membership",
        ["segment_id"],
    )

    op.create_index("ix_contact_import_job_org_id", "contact_import_job", ["org_id"])
    op.create_index(
        "ix_contact_import_job_org_status",
        "contact_import_job",
        ["org_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_contact_import_job_org_status", table_name="contact_import_job")
    op.drop_index("ix_contact_import_job_org_id", table_name="contact_import_job")
    op.drop_table("contact_import_job")

    op.drop_index(
        "ix_contact_segment_membership_segment_id",
        table_name="contact_segment_membership",
    )
    op.drop_index(
        "ix_contact_segment_membership_contact_id",
        table_name="contact_segment_membership",
    )
    op.drop_index("ix_contact_segment_membership_org_id", table_name="contact_segment_membership")
    op.drop_table("contact_segment_membership")

    op.drop_index("ix_contact_segment_org_id", table_name="contact_segment")
    op.drop_table("contact_segment")

    op.drop_index(
        "ix_contact_channel_opt_in_channel_address",
        table_name="contact_channel_opt_in",
    )
    op.drop_index(
        "ix_contact_channel_opt_in_contact_id",
        table_name="contact_channel_opt_in",
    )
    op.drop_index("ix_contact_channel_opt_in_org_id", table_name="contact_channel_opt_in")
    op.drop_table("contact_channel_opt_in")

    op.drop_index("ix_contact_phone", table_name="contact")
    op.drop_index("ix_contact_email", table_name="contact")
    op.drop_index("ix_contact_external_id", table_name="contact")
    op.drop_index("ix_contact_org_id", table_name="contact")
    op.drop_table("contact")

    opt_in_status_enum = postgresql.ENUM(name="optinstatusenum")
    import_status_enum = postgresql.ENUM(name="contactimportstatusenum")
    contact_status_enum = postgresql.ENUM(name="contactstatusenum")

    opt_in_status_enum.drop(op.get_bind(), checkfirst=False)
    import_status_enum.drop(op.get_bind(), checkfirst=False)
    contact_status_enum.drop(op.get_bind(), checkfirst=False)
