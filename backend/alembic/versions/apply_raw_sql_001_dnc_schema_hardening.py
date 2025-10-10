"""Apply raw SQL: 001_dnc_schema_hardening.sql

Revision ID: apply_raw_sql_001
Revises: optimize_dnc_history_indexes
Create Date: 2025-10-10 16:45:00
"""
from alembic import op
import sqlalchemy as sa  # noqa: F401
import os


revision = 'apply_raw_sql_001'
down_revision = 'optimize_dnc_history_indexes'
branch_labels = None
depends_on = None


def _read_sql(filename: str) -> str:
    here = os.path.dirname(__file__)
    # Primary: backend/sql/migrations
    backend_root = os.path.abspath(os.path.join(here, '..', '..'))
    path = os.path.join(backend_root, 'sql', 'migrations', filename)
    if not os.path.exists(path):
        # Fallback: repo_root/backend/sql/migrations
        repo_root = os.path.abspath(os.path.join(backend_root, '..'))
        alt = os.path.join(repo_root, 'backend', 'sql', 'migrations', filename)
        path = alt
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def upgrade():
    sql = _read_sql('001_dnc_schema_hardening.sql')
    op.execute(sql)


def downgrade():
    # Best-effort partial rollback of schema objects created in the SQL
    op.execute(
        """
        -- Drop triggers and functions created by 001 if present
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_dnc_entries_set_updated_at') THEN
            DROP TRIGGER trg_dnc_entries_set_updated_at ON dnc_entries;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='set_updated_at') THEN
            DROP FUNCTION IF EXISTS set_updated_at();
          END IF;
          IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_dnc_requests_set_last_updated') THEN
            DROP TRIGGER trg_dnc_requests_set_last_updated ON dnc_requests;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='set_last_updated_at') THEN
            DROP FUNCTION IF EXISTS set_last_updated_at();
          END IF;
        END $$;
        """
    )


