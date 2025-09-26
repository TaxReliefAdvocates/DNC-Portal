"""Add DNC sync tables

Revision ID: add_dnc_sync_tables
Revises: 
Create Date: 2025-09-26 15:43:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_dnc_sync_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create master_dnc_entries table
    op.create_table('master_dnc_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=False),
        sa.Column('convoso_lead_id', sa.String(length=50), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('campaign_name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_master_dnc_entries_id'), 'master_dnc_entries', ['id'], unique=False)
    op.create_index(op.f('ix_master_dnc_entries_phone_number'), 'master_dnc_entries', ['phone_number'], unique=True)

    # Create dnc_sync_statuses table
    op.create_table('dnc_sync_statuses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dnc_entry_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('provider_id', sa.String(length=100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dnc_entry_id'], ['master_dnc_entries.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dnc_entry_id', 'provider', name='uq_dnc_entry_provider')
    )
    op.create_index(op.f('ix_dnc_sync_statuses_id'), 'dnc_sync_statuses', ['id'], unique=False)
    op.create_index('idx_dnc_sync_provider_status', 'dnc_sync_statuses', ['provider', 'status'], unique=False)

    # Create dnc_sync_jobs table
    op.create_table('dnc_sync_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('total_entries', sa.Integer(), nullable=False),
        sa.Column('processed_entries', sa.Integer(), nullable=False),
        sa.Column('successful_syncs', sa.Integer(), nullable=False),
        sa.Column('failed_syncs', sa.Integer(), nullable=False),
        sa.Column('skipped_syncs', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dnc_sync_jobs_id'), 'dnc_sync_jobs', ['id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_dnc_sync_jobs_id'), table_name='dnc_sync_jobs')
    op.drop_table('dnc_sync_jobs')
    op.drop_index('idx_dnc_sync_provider_status', table_name='dnc_sync_statuses')
    op.drop_index(op.f('ix_dnc_sync_statuses_id'), table_name='dnc_sync_statuses')
    op.drop_table('dnc_sync_statuses')
    op.drop_index(op.f('ix_master_dnc_entries_phone_number'), table_name='master_dnc_entries')
    op.drop_index(op.f('ix_master_dnc_entries_id'), table_name='master_dnc_entries')
    op.drop_table('master_dnc_entries')
