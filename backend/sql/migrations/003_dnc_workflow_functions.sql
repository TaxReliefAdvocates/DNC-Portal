-- 003_dnc_workflow_functions.sql
-- Purpose: Provide transactional helper functions and triggers for the DNC workflow

BEGIN;

-- Helper: insert 5 propagation attempts for a request
CREATE OR REPLACE FUNCTION dnc_create_propagation_attempts(p_org int, p_phone text, p_request_id int)
RETURNS void AS $$
BEGIN
  INSERT INTO propagation_attempts (organization_id, phone_e164, service_key, status, started_at, request_id)
  VALUES 
    (p_org, p_phone, 'ringcentral', 'pending', now(), p_request_id),
    (p_org, p_phone, 'convoso',    'pending', now(), p_request_id),
    (p_org, p_phone, 'ytel',       'pending', now(), p_request_id),
    (p_org, p_phone, 'logics',     'pending', now(), p_request_id),
    (p_org, p_phone, 'genesys',    'pending', now(), p_request_id);
END;$$ LANGUAGE plpgsql;


-- Transactional approval: approve request, upsert org DNC entry, create attempts
CREATE OR REPLACE FUNCTION approve_dnc_request_tx(p_request_id int, p_reviewer int, p_notes text)
RETURNS void AS $$
DECLARE
  v_org   int;
  v_phone text;
BEGIN
  -- Lock the request row to avoid races
  SELECT organization_id, phone_e164 INTO v_org, v_phone
  FROM dnc_requests
  WHERE id = p_request_id
  FOR UPDATE;

  IF v_org IS NULL THEN
    RAISE EXCEPTION 'Request % not found', p_request_id;
  END IF;

  -- Update request
  UPDATE dnc_requests
     SET status = 'approved',
         reviewed_by_user_id = p_reviewer,
         decision_notes = p_notes,
         approved_at = now(),
         last_updated_at = now()
   WHERE id = p_request_id;

  -- Upsert DNC entry
  INSERT INTO dnc_entries (organization_id, phone_e164, active, created_at, updated_at, notes, request_id, source)
  VALUES (v_org, v_phone, true, now(), now(), p_notes, p_request_id, 'user_request')
  ON CONFLICT (organization_id, phone_e164)
  DO UPDATE SET active = true, removed_at = NULL, updated_at = now(), notes = EXCLUDED.notes, request_id = EXCLUDED.request_id;

  -- Create attempts
  PERFORM dnc_create_propagation_attempts(v_org, v_phone, p_request_id);

  -- Mark propagation started timestamp
  UPDATE dnc_requests
     SET propagation_started_at = COALESCE(propagation_started_at, now()),
         last_updated_at = now()
   WHERE id = p_request_id;
END;$$ LANGUAGE plpgsql;


-- Trigger: when an attempt becomes in_progress, set propagation_started_at if null
CREATE OR REPLACE FUNCTION trg_attempt_in_progress_set_request_started()
RETURNS trigger AS $$
BEGIN
  IF NEW.status = 'in_progress' THEN
    UPDATE dnc_requests
       SET propagation_started_at = COALESCE(propagation_started_at, now()),
           last_updated_at = now()
     WHERE (id = NEW.request_id)
        OR (organization_id = NEW.organization_id AND phone_e164 = NEW.phone_e164);
  END IF;
  RETURN NEW;
END;$$ LANGUAGE plpgsql;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_attempt_in_progress') THEN
    CREATE TRIGGER trg_attempt_in_progress
      AFTER UPDATE OF status ON propagation_attempts
      FOR EACH ROW
      WHEN (NEW.status = 'in_progress')
      EXECUTE FUNCTION trg_attempt_in_progress_set_request_started();
  END IF;
END$$;


-- Trigger: when an attempt finishes (success/failed), evaluate request completion
CREATE OR REPLACE FUNCTION trg_attempt_finished_mark_request_complete()
RETURNS trigger AS $$
BEGIN
  IF NEW.status IN ('success','failed') THEN
    PERFORM mark_request_completed_if_done(NEW.organization_id, NEW.phone_e164);
  END IF;
  RETURN NEW;
END;$$ LANGUAGE plpgsql;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_attempt_finished') THEN
    CREATE TRIGGER trg_attempt_finished
      AFTER UPDATE OF status ON propagation_attempts
      FOR EACH ROW
      WHEN (NEW.status IN ('success','failed'))
      EXECUTE FUNCTION trg_attempt_finished_mark_request_complete();
  END IF;
END$$;

COMMIT;


