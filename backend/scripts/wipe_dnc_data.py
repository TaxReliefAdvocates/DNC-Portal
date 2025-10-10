from sqlalchemy import text
from do_not_call.core.database import SessionLocal


SQL = """
TRUNCATE TABLE dnc_events CASCADE;
TRUNCATE TABLE propagation_attempts CASCADE;
TRUNCATE TABLE dnc_entries CASCADE;
TRUNCATE TABLE dnc_requests CASCADE;

ALTER SEQUENCE IF EXISTS dnc_requests_id_seq RESTART WITH 1;
ALTER SEQUENCE IF EXISTS dnc_entries_id_seq RESTART WITH 1;
ALTER SEQUENCE IF EXISTS propagation_attempts_id_seq RESTART WITH 1;
ALTER SEQUENCE IF EXISTS dnc_events_id_seq RESTART WITH 1;

"""

VERIFY = """
SELECT 'dnc_requests' as table_name, COUNT(*) as count FROM dnc_requests
UNION ALL
SELECT 'dnc_entries', COUNT(*) FROM dnc_entries
UNION ALL
SELECT 'propagation_attempts', COUNT(*) FROM propagation_attempts
UNION ALL
SELECT 'dnc_events', COUNT(*) FROM dnc_events;
"""


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(text(SQL))
        db.commit()
        rows = db.execute(text(VERIFY)).fetchall()
        print("Verification counts (should all be 0):")
        for r in rows:
            print(f"{r[0]}\t{r[1]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()


