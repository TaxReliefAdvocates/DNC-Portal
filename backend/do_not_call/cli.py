#!/usr/bin/env python3
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
import random
import typer
from typing import Optional
from sqlalchemy import text, inspect

from .config import settings
from .core.database import create_tables, get_db, Base, engine
from .core.models import (
    PhoneNumber,
    CRMStatus,
    Organization,
    User,
    OrgUser,
    ServiceCatalog,
    OrgService,
    DNCEntry,
    RemovalJob,
    RemovalJobItem,
    DNCRequest,
)
from passlib.context import CryptContext


app = typer.Typer(help="DNC Portal backend CLI")
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


@app.callback()
def main() -> None:
    """Utilities for DB setup, seeding, and diagnostics.

    DATABASE_URL is read from environment or `do_not_call/config.py` Settings.
    For Supabase, set DATABASE_URL to the full Postgres connection string with
    ?sslmode=require.
    """


@app.command("db-url")
def db_url() -> None:
    """Print the active DATABASE_URL."""
    typer.echo(settings.DATABASE_URL)


@app.command("ping")
def ping() -> None:
    """Test DB connectivity (SELECT 1)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        typer.secho("DB connection OK", fg=typer.colors.GREEN)
    except Exception as exc:
        typer.secho(f"DB connection failed: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command("create")
def create() -> None:
    """Create all tables for the application."""
    create_tables()
    typer.secho("Tables created", fg=typer.colors.GREEN)


@app.command("drop")
def drop(confirm: bool = typer.Option(False, "--confirm", help="Confirm dropping ALL tables")) -> None:
    """DROP ALL TABLES (irreversible)."""
    if not confirm:
        typer.secho("Pass --confirm to drop all tables", fg=typer.colors.YELLOW)
        raise typer.Exit(code=2)
    Base.metadata.drop_all(bind=engine)
    typer.secho("All tables dropped", fg=typer.colors.RED)


@app.command("reset")
def reset() -> None:
    """Drop and recreate all tables."""
    Base.metadata.drop_all(bind=engine)
    create_tables()
    typer.secho("Tables reset", fg=typer.colors.GREEN)


@app.command("schema-report")
def schema_report(include_counts: bool = typer.Option(False, help="Include row counts (may be slow)")) -> None:
    """Print a comprehensive schema report: tables, columns, PK/FK, indexes, and counts."""
    insp = inspect(engine)
    out_lines: list[str] = []
    try:
        for tbl in sorted(insp.get_table_names()):
            out_lines.append(f"\n== Table: {tbl} ==")
            # Columns
            cols = insp.get_columns(tbl)
            for c in cols:
                typ = str(c.get("type"))
                nullable = c.get("nullable")
                default = c.get("default")
                out_lines.append(f"  - {c['name']}: {typ}, nullable={nullable}, default={default}")
            # PK
            pk = insp.get_pk_constraint(tbl)
            if pk and pk.get("constrained_columns"):
                out_lines.append(f"  PK: {', '.join(pk['constrained_columns'])}")
            # FKs
            fks = insp.get_foreign_keys(tbl)
            for fk in fks:
                cols = ", ".join(fk.get("constrained_columns", []))
                ref = f"{fk.get('referred_table')}({', '.join(fk.get('referred_columns', []))})"
                out_lines.append(f"  FK: ({cols}) -> {ref}")
            # Indexes
            indexes = insp.get_indexes(tbl)
            for ix in indexes:
                out_lines.append(f"  IDX: {ix.get('name')} cols={', '.join(ix.get('column_names', []) )} unique={ix.get('unique')}")
            # Count
            if include_counts:
                try:
                    with engine.connect() as conn:
                        res = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
                        cnt = res.scalar_one()
                        out_lines.append(f"  ROWS: {cnt}")
                except Exception as ce:
                    out_lines.append(f"  ROWS: error: {ce}")
        typer.echo("\n".join(out_lines))
    except Exception as exc:
        typer.secho(f"Schema inspection failed: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command("seed")
def seed(org_name: str = "Test Org", org_slug: str = "test-org") -> None:
    """Seed database with sample data suitable for dev/testing."""
    create_tables()
    db = next(get_db())
    try:
        # Organization and admin user
        org = Organization(name=org_name, slug=org_slug)
        db.add(org)
        admin = User(email="admin@example.com", name="Admin User", role="owner", is_super_admin=True,
                     password_hash=pwd_ctx.hash("admin"))
        db.add(admin)
        db.flush()
        db.add(OrgUser(organization_id=org.id, user_id=admin.id, role="owner"))

        # Service catalog + org services
        services = [
            ("convoso", "Convoso"),
            ("ytel", "Ytel"),
            ("ringcentral", "Ring Central"),
            ("genesys", "Genesys"),
            ("logics", "Logics"),
        ]
        for key, name in services:
            if not db.query(ServiceCatalog).filter_by(key=key).first():
                db.add(ServiceCatalog(key=key, name=name))
        db.flush()
        for key, _ in services:
            if not db.query(OrgService).filter_by(organization_id=org.id, service_key=key).first():
                db.add(OrgService(organization_id=org.id, service_key=key, is_active=True))

        # Sample phone numbers
        sample_numbers = [f"+15551234{n:03d}" for n in range(100, 116)]
        phone_rows: list[PhoneNumber] = []
        for idx, pn in enumerate(sample_numbers):
            row = PhoneNumber(
                phone_number=pn,
                status="active",
                notes=f"Seed number {idx+1}",
                created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 14)),
            )
            db.add(row)
            phone_rows.append(row)
        db.commit()

        # Seed org-level DNC entries
        for pn in sample_numbers[:5]:
            db.add(
                DNCEntry(
                    organization_id=org.id,
                    phone_e164=pn.replace("+", ""),
                    reason="customer opt-out",
                    source="manual",
                    created_by_user_id=admin.id,
                )
            )
        db.commit()

        # Seed a removal job with three items
        job = RemovalJob(
            organization_id=org.id,
            submitted_by_user_id=admin.id,
            notes="Initial test job",
            total=3,
            status="pending",
        )
        db.add(job)
        db.flush()
        for pn in sample_numbers[:3]:
            db.add(RemovalJobItem(job_id=job.id, phone_e164=pn.replace("+", ""), status="pending"))
        db.commit()

        # Seed DNC Requests (pending/approved/denied)
        statuses = ["pending", "approved", "denied"]
        for i in range(15):
            status = random.choice(statuses)
            created_at = datetime.now(timezone.utc) - timedelta(days=random.randint(0, 10))
            decided_at = created_at + timedelta(days=random.randint(0, 3)) if status != "pending" else None
            req = DNCRequest(
                organization_id=org.id,
                phone_e164=sample_numbers[i % len(sample_numbers)].replace("+", ""),
                reason=random.choice(["customer opt-out", "internal block", "litigation risk"]),
                channel=random.choice(["sms", "voice", "email"]),
                status=status,
                requested_by_user_id=admin.id,
                reviewed_by_user_id=admin.id if status != "pending" else None,
                decision_notes=("auto-approved for test" if status == "approved" else ("auto-denied for test" if status == "denied" else None)),
                created_at=created_at,
                decided_at=decided_at,
            )
            db.add(req)
        db.commit()

        typer.secho("Seed data inserted (org/user/services/phones/DNC entries/requests/jobs)", fg=typer.colors.GREEN)
    finally:
        db.close()


if __name__ == "__main__":
    app()


