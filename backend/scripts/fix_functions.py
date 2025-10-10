from sqlalchemy import text
from do_not_call.core.database import SessionLocal


SQL = """
CREATE OR REPLACE FUNCTION dnc_create_propagation_attempts(p_org int, p_phone text, p_request_id int)
RETURNS void AS $$
BEGIN
  INSERT INTO propagation_attempts (organization_id, phone_e164, service_key, status, started_at, request_id, attempt_no)
  VALUES 
    (p_org, p_phone, 'ringcentral', 'pending', now(), p_request_id, 1),
    (p_org, p_phone, 'convoso',    'pending', now(), p_request_id, 1),
    (p_org, p_phone, 'ytel',       'pending', now(), p_request_id, 1),
    (p_org, p_phone, 'logics',     'pending', now(), p_request_id, 1),
    (p_org, p_phone, 'genesys',    'pending', now(), p_request_id, 1);
END;$$ LANGUAGE plpgsql;
"""


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(text(SQL))
        db.commit()
        print("Updated dnc_create_propagation_attempts to set attempt_no=1 explicitly.")
    finally:
        db.close()


if __name__ == "__main__":
    main()


