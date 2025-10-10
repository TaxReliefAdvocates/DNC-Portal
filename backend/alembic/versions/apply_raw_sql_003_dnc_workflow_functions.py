"""Apply raw SQL: 003_dnc_workflow_functions.sql

Revision ID: apply_raw_sql_003
Revises: apply_raw_sql_002
Create Date: 2025-10-10 16:47:00
"""
from alembic import op
import sqlalchemy as sa  # noqa: F401
import os


revision = 'apply_raw_sql_003'
down_revision = 'apply_raw_sql_002'
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
    sql = _read_sql('003_dnc_workflow_functions.sql')
    op.execute(sql)


def downgrade():
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_attempt_in_progress ON propagation_attempts;
        DROP TRIGGER IF EXISTS trg_attempt_finished ON propagation_attempts;
        DROP FUNCTION IF EXISTS trg_attempt_in_progress_set_request_started();
        DROP FUNCTION IF EXISTS trg_attempt_finished_mark_request_complete();
        DROP FUNCTION IF EXISTS dnc_create_propagation_attempts(int, text, int);
        DROP FUNCTION IF EXISTS approve_dnc_request_tx(int, int, text);
        """
    )


