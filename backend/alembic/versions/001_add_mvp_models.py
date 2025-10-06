"""add_mvp_models

Revision ID: 001_add_mvp_models
Revises: 
Create Date: 2025-10-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_add_mvp_models'
down_revision = None
next_revision = None


def upgrade():
    # Add baseline_cost_minor to message_event
    op.add_column('message_event', sa.Column('baseline_cost_minor', sa.Integer(), nullable=True))
    
    # Add org_id to provider and unique constraint
    op.add_column('provider', sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('provider_org_id_fkey', 'provider', 'organization', ['org_id'], ['id'])
    op.create_index(op.f('ix_provider_org_id'), 'provider', ['org_id'], unique=False)
    
    # Update existing providers to have org_id (if any exist, assign to first org)
    # This is for migration only - in production, this should be handled differently
    op.execute("""
        UPDATE provider 
        SET org_id = (SELECT id FROM organization LIMIT 1) 
        WHERE org_id IS NULL
    """)
    
    # Make org_id not nullable after update
    op.alter_column('provider', 'org_id', nullable=False)
    
    # Drop old unique constraint on name and create new one with org_id
    op.drop_constraint('provider_name_key', 'provider', type_='unique')
    op.create_unique_constraint('_org_provider_name_uc', 'provider', ['org_id', 'name'])
    
    # Add unique constraint for idempotency on message_job
    op.create_unique_constraint('_org_idempotency_uc', 'message_job', ['org_id', 'idempotency_key'])
    
    # Add price_table_version to cost_record for audit trail
    op.add_column('cost_record', sa.Column('price_table_version', sa.String(), nullable=True))


def downgrade():
    # Remove price_table_version from cost_record
    op.drop_column('cost_record', 'price_table_version')
    
    # Remove unique constraint from message_job
    op.drop_constraint('_org_idempotency_uc', 'message_job', type_='unique')
    
    # Remove unique constraint
    op.drop_constraint('_org_provider_name_uc', 'provider', type_='unique')
    op.create_unique_constraint('provider_name_key', 'provider', ['name'])
    
    # Remove org_id from provider
    op.drop_index(op.f('ix_provider_org_id'), table_name='provider')
    op.drop_constraint('provider_org_id_fkey', 'provider', type_='foreignkey')
    op.drop_column('provider', 'org_id')
    
    # Remove baseline_cost_minor from message_event
    op.drop_column('message_event', 'baseline_cost_minor')
