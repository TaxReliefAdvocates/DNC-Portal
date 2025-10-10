from sqlalchemy import text
from do_not_call.core.database import SessionLocal


SQL = """
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ck_propagation_attempts_status_valid'
  ) THEN
    ALTER TABLE propagation_attempts DROP CONSTRAINT ck_propagation_attempts_status_valid;
  END IF;
END$$;

ALTER TABLE propagation_attempts
  ADD CONSTRAINT ck_propagation_attempts_status_valid
  CHECK (status IN ('pending','in_progress','success','failed','skipped'));
"""


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(text(SQL))
        db.commit()
        print("Updated propagation_attempts status check to include 'skipped'.")
    finally:
        db.close()


if __name__ == "__main__":
    main()


