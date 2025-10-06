"""keep historical migration metadata after base schema

Revision ID: 001_add_mvp_models
Revises: 000_base_schema
Create Date: 2025-10-06

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "001_add_mvp_models"
down_revision = "000_base_schema"
next_revision = None


def upgrade():
    """Schema already covered by 000_base_schema."""
    # This migration is intentionally a no-op because the consolidated
    # base schema already includes the MVP adjustments.
    op.get_bind()


def downgrade():
    # Nothing to rollback because upgrade made no changes.
    op.get_bind()
