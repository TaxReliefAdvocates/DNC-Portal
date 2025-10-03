"""Add search history table

Revision ID: add_search_history_table
Revises: add_dnc_sync_tables
Create Date: 2025-10-03 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_search_history_table'
down_revision = 'add_dnc_sync_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create search_history table
    op.create_table('search_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('phone_number', sa.String(length=20), nullable=False),
        sa.Column('search_results', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_search_history_id'), 'search_history', ['id'], unique=False)
    op.create_index(op.f('ix_search_history_organization_id'), 'search_history', ['organization_id'], unique=False)
    op.create_index(op.f('ix_search_history_phone_number'), 'search_history', ['phone_number'], unique=False)
    op.create_index(op.f('ix_search_history_user_id'), 'search_history', ['user_id'], unique=False)
    op.create_index('idx_org_created', 'search_history', ['organization_id', 'created_at'], unique=False)
    op.create_index('idx_user_created', 'search_history', ['user_id', 'created_at'], unique=False)


def downgrade():
    op.drop_index('idx_user_created', table_name='search_history')
    op.drop_index('idx_org_created', table_name='search_history')
    op.drop_index(op.f('ix_search_history_user_id'), table_name='search_history')
    op.drop_index(op.f('ix_search_history_phone_number'), table_name='search_history')
    op.drop_index(op.f('ix_search_history_organization_id'), table_name='search_history')
    op.drop_index(op.f('ix_search_history_id'), table_name='search_history')
    op.drop_table('search_history')
