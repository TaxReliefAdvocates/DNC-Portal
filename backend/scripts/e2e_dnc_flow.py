from __future__ import annotations

import time
from datetime import datetime
from typing import List

from sqlalchemy import text

from do_not_call.core.database import SessionLocal
from do_not_call.api.v1.tenants import _propagate_approved_entry_with_systems_check


def sql(db, q: str, params: dict | None = None):
    return db.execute(text(q), params or {})


def fmt(ts: str | None) -> str:
    return ts or ''


def wipe(db) -> None:
    sql(db, "TRUNCATE TABLE dnc_events CASCADE;")
    sql(db, "TRUNCATE TABLE propagation_attempts CASCADE;")
    sql(db, "TRUNCATE TABLE dnc_entries CASCADE;")
    sql(db, "TRUNCATE TABLE dnc_requests CASCADE;")
    sql(db, "ALTER SEQUENCE IF EXISTS dnc_requests_id_seq RESTART WITH 1;")
    sql(db, "ALTER SEQUENCE IF EXISTS dnc_entries_id_seq RESTART WITH 1;")
    sql(db, "ALTER SEQUENCE IF EXISTS propagation_attempts_id_seq RESTART WITH 1;")
    sql(db, "ALTER SEQUENCE IF EXISTS dnc_events_id_seq RESTART WITH 1;")
    db.commit()


def verify_counts(db) -> list[tuple[str, int]]:
    rows = sql(db, (
        "SELECT 'dnc_requests' as table_name, COUNT(*) as count FROM dnc_requests\n"
        "UNION ALL SELECT 'dnc_entries', COUNT(*) FROM dnc_entries\n"
        "UNION ALL SELECT 'propagation_attempts', COUNT(*) FROM propagation_attempts\n"
        "UNION ALL SELECT 'dnc_events', COUNT(*) FROM dnc_events\n"
    )).fetchall()
    return [(r[0], int(r[1])) for r in rows]


def create_request(db, org_id: int, phone_e164: str, reason: str, channel: str, user_id: int) -> int:
    row = sql(db, (
        "INSERT INTO dnc_requests (organization_id, phone_e164, reason, channel, requested_by_user_id, status, submitted_at)\n"
        "VALUES (:org, :phone, :reason, :channel, :uid, 'pending', now()) RETURNING id;"
    ), {"org": org_id, "phone": phone_e164, "reason": reason, "channel": channel, "uid": user_id}).fetchone()
    db.commit()
    return int(row[0])


def approve_request(db, request_id: int, reviewer_id: int, notes: str) -> None:
    sql(db, "SELECT approve_dnc_request_tx(:rid, :rev, :notes)", {"rid": request_id, "rev": reviewer_id, "notes": notes})
    db.commit()


def list_attempts(db, request_id: int) -> list[dict]:
    rows = sql(db, (
        "SELECT service_key, status, attempt_no, started_at, finished_at, http_status FROM propagation_attempts WHERE request_id = :rid ORDER BY service_key, attempt_no"
    ), {"rid": request_id}).mappings().all()
    return [dict(r) for r in rows]


def summary_tables(db) -> list[tuple]:
    rows = sql(db, (
        "SELECT 'Requests' as type, status, COUNT(*) as count FROM dnc_requests GROUP BY status\n"
        "UNION ALL SELECT 'Entries' as type, CASE WHEN active THEN 'active' ELSE 'inactive' END as status, COUNT(*) FROM dnc_entries GROUP BY active\n"
        "UNION ALL SELECT 'Attempts' as type, status, COUNT(*) FROM propagation_attempts GROUP BY status\n"
        "UNION ALL SELECT 'Events' as type, action as event_type, COUNT(*) FROM dnc_events GROUP BY action\n"
    )).fetchall()
    return rows


def latest_requests(db):
    rows = sql(db, (
        "SELECT r.id, r.phone_e164, r.status, r.submitted_at, r.completed_at,\n"
        "COUNT(pa.id) as total_attempts,\n"
        "COUNT(CASE WHEN pa.status = 'success' THEN 1 END) as success_count,\n"
        "COUNT(CASE WHEN pa.status = 'failed' THEN 1 END) as failed_count\n"
        "FROM dnc_requests r LEFT JOIN propagation_attempts pa ON r.id = pa.request_id\n"
        "GROUP BY r.id ORDER BY r.id DESC LIMIT 10;"
    )).fetchall()
    return rows


def main():
    db = SessionLocal()
    try:
        print("Wiping tables…")
        wipe(db)
        print("Counts after wipe:")
        print(verify_counts(db))

        # Test 1
        print("\nTest 1: Basic submission → approval → propagation")
        rid = create_request(db, 1, "+15551234567", "Customer opt-out", "voice", 1)
        print(f"Created request id={rid}")
        approve_request(db, rid, reviewer_id=1, notes="Test approval")
        print("Approved; launching background propagation…")
        # call background function (sync run)
        _propagate_approved_entry_with_systems_check(rid, 1, "+15551234567")
        at = list_attempts(db, rid)
        print(f"Attempts: {at}")

        # Test 2: multiple & bulk approve
        print("\nTest 2: Multiple requests & bulk approve")
        rids: List[int] = []
        for p in ["+15551234568", "+15551234569", "+15551234570"]:
            rids.append(create_request(db, 1, p, "Legal request", "voice", 1))
        for r in rids:
            approve_request(db, r, reviewer_id=1, notes="Bulk approve")
            _propagate_approved_entry_with_systems_check(r, 1, sql(db, "SELECT phone_e164 FROM dnc_requests WHERE id=:r", {"r": r}).scalar())
        print("Bulk approved and propagated.")

        # Test 3: Retry failed (force mark one failed and retry logic simulated by adding new attempt_no)
        print("\nTest 3: Retry a failed")
        sql(db, (
            "UPDATE propagation_attempts SET status='failed', error_message='Test failure' \n"
            "WHERE request_id=:rid AND service_key='genesys' AND attempt_no=1"
        ), {"rid": rid})
        db.commit()
        # create a new pending attempt for genesys
        sql(db, (
            "INSERT INTO propagation_attempts (organization_id, request_id, phone_e164, service_key, attempt_no, status, started_at)\n"
            "SELECT organization_id, id, phone_e164, 'genesys', 2, 'pending', now() FROM dnc_requests WHERE id=:rid"
        ), {"rid": rid})
        db.commit()
        print("Forced fail and inserted retry attempt #2 (pending)")

        # Test 4: Rejection
        print("\nTest 4: Rejection flow")
        rid_reject = create_request(db, 1, "+15551234571", "Invalid number", "voice", 1)
        sql(db, "UPDATE dnc_requests SET status='denied', decided_at=now(), decision_notes='Invalid number' WHERE id=:rid", {"rid": rid_reject})
        db.commit()
        print(f"Rejected request id={rid_reject}")

        # Summary
        print("\nSummary tables:")
        for r in summary_tables(db):
            print(r)
        print("\nLatest requests:")
        for r in latest_requests(db):
            print(r)
    finally:
        db.close()


if __name__ == "__main__":
    main()


