"""Optimize DNC history indexes

Revision ID: optimize_dnc_history_indexes
Revises: add_search_history_table
Create Date: 2025-01-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'optimize_dnc_history_indexes'
down_revision = 'add_search_history_table'
branch_labels = None
depends_on = None


def upgrade():
    """Add optimized indexes for DNC history queries"""
    
    # Add index for propagation attempts by started_at for better sorting
    op.create_index(
        'ix_propagation_attempts_started_at_desc',
        'propagation_attempts',
        [sa.text('started_at DESC')],
        unique=False
    )
    
    # Add composite index for org + service + status for filtering
    op.create_index(
        'ix_propagation_attempts_org_service_status',
        'propagation_attempts',
        ['organization_id', 'service_key', 'status'],
        unique=False
    )
    
    # Add index for DNC requests by decided_at for better sorting
    op.create_index(
        'ix_dnc_requests_decided_at_desc',
        'dnc_requests',
        [sa.text('decided_at DESC')],
        unique=False
    )
    
    # Add composite index for DNC requests filtering
    op.create_index(
        'ix_dnc_requests_org_status_created',
        'dnc_requests',
        ['organization_id', 'status', 'created_at'],
        unique=False
    )


def downgrade():
    """Remove the optimized indexes"""
    
    op.drop_index('ix_dnc_requests_org_status_created', table_name='dnc_requests')
    op.drop_index('ix_dnc_requests_decided_at_desc', table_name='dnc_requests')
    op.drop_index('ix_propagation_attempts_org_service_status', table_name='propagation_attempts')
    op.drop_index('ix_propagation_attempts_started_at_desc', table_name='propagation_attempts')
