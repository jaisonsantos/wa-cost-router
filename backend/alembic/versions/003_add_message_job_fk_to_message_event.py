"""add message_job reference to message_event"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_add_message_job_fk_to_message_event'
down_revision = '002_encrypt_provider_credentials'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'message_event',
        sa.Column('message_job_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_message_event_message_job_id_message_job',
        'message_event',
        'message_job',
        ['message_job_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_message_event_message_job_id_message_job',
        'message_event',
        type_='foreignkey',
    )
    op.drop_column('message_event', 'message_job_id')
