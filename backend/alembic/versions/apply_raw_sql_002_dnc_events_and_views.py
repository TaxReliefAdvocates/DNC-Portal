"""Apply raw SQL: 002_dnc_events_and_views.sql

Revision ID: apply_raw_sql_002
Revises: apply_raw_sql_001
Create Date: 2025-10-10 16:46:00
"""
from alembic import op
import sqlalchemy as sa  # noqa: F401
import os


revision = 'apply_raw_sql_002'
down_revision = 'apply_raw_sql_001'
branch_labels = None
depends_on = None


def _read_sql(filename: str) -> str:
    here = os.path.dirname(__file__)
    backend_root = os.path.abspath(os.path.join(here, '..', '..'))
    path = os.path.join(backend_root, 'sql', 'migrations', filename)
    if not os.path.exists(path):
        repo_root = os.path.abspath(os.path.join(backend_root, '..'))
        path = os.path.join(repo_root, 'backend', 'sql', 'migrations', filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def upgrade():
    sql = _read_sql('002_dnc_events_and_views.sql')
    op.execute(sql)


def downgrade():
    op.execute(
        """
        DROP VIEW IF EXISTS vw_dnc_request_status;
        DROP TABLE IF EXISTS dnc_events;
        DROP FUNCTION IF EXISTS mark_request_completed_if_done(int, text);
        """
    )


