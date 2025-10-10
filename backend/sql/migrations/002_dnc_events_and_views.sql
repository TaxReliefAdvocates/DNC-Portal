-- 002_dnc_events_and_views.sql
-- Purpose: Add event/audit tables, helper views, and convenience functions for the DNC workflow

BEGIN;

-- Event log for immutable audit trail
CREATE TABLE IF NOT EXISTS dnc_events (
  id              bigserial PRIMARY KEY,
  occurred_at     timestamptz NOT NULL DEFAULT now(),
  level           text        NOT NULL CHECK (level IN ('info','warn','error')),
  component       text        NOT NULL,
  action          text        NOT NULL,
  organization_id integer,
  request_id      integer,
  phone_e164      text,
  service_key     text,
  user_id         integer,
  details         jsonb
);

CREATE INDEX IF NOT EXISTS idx_dnc_events_when            ON dnc_events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_dnc_events_req             ON dnc_events(request_id);
CREATE INDEX IF NOT EXISTS idx_dnc_events_org_phone       ON dnc_events(organization_id, phone_e164);
CREATE INDEX IF NOT EXISTS idx_dnc_events_component_action ON dnc_events(component, action);


-- Helper view: request with propagation rollup
CREATE OR REPLACE VIEW vw_dnc_request_status AS
SELECT
  r.id                         AS request_id,
  r.organization_id,
  r.phone_e164,
  r.status                     AS request_status,
  r.submitted_at,
  r.approved_at,
  r.rejected_at,
  r.propagation_started_at,
  r.propagation_completed_at,
  r.completed_at,
  COALESCE(SUM(CASE WHEN a.status = 'success' THEN 1 ELSE 0 END),0) AS success_count,
  COALESCE(SUM(CASE WHEN a.status = 'failed'  THEN 1 ELSE 0 END),0) AS failed_count,
  COALESCE(SUM(CASE WHEN a.status = 'pending' THEN 1 ELSE 0 END),0) AS pending_count,
  COALESCE(SUM(CASE WHEN a.status = 'in_progress' THEN 1 ELSE 0 END),0) AS in_progress_count,
  MAX(a.finished_at) AS last_finished_at
FROM dnc_requests r
LEFT JOIN propagation_attempts a
  ON a.organization_id = r.organization_id
 AND a.phone_e164      = r.phone_e164
 AND (a.request_id IS NULL OR a.request_id = r.id)
GROUP BY r.id, r.organization_id, r.phone_e164, r.status,
         r.submitted_at, r.approved_at, r.rejected_at,
         r.propagation_started_at, r.propagation_completed_at, r.completed_at;


-- Convenience function: mark request completed when all attempts finished
CREATE OR REPLACE FUNCTION mark_request_completed_if_done(p_org int, p_phone text)
RETURNS void AS $$
DECLARE
  v_req_id int;
  v_total  int;
  v_done   int;
BEGIN
  SELECT id INTO v_req_id
  FROM dnc_requests
  WHERE organization_id = p_org AND phone_e164 = p_phone
  ORDER BY id DESC
  LIMIT 1;

  IF v_req_id IS NULL THEN
    RETURN;
  END IF;

  SELECT count(*) INTO v_total
  FROM propagation_attempts
  WHERE organization_id = p_org AND phone_e164 = p_phone AND request_id = v_req_id;

  SELECT count(*) INTO v_done
  FROM propagation_attempts
  WHERE organization_id = p_org AND phone_e164 = p_phone AND request_id = v_req_id
    AND status IN ('success','failed');

  IF v_total > 0 AND v_total = v_done THEN
    UPDATE dnc_requests
      SET status = CASE WHEN EXISTS (
                            SELECT 1 FROM propagation_attempts 
                            WHERE organization_id = p_org AND phone_e164 = p_phone AND request_id = v_req_id AND status = 'failed'
                          ) THEN 'completed' ELSE 'completed' END,
          propagation_completed_at = now(),
          completed_at = now(),
          last_updated_at = now()
    WHERE id = v_req_id;
  END IF;
END;$$ LANGUAGE plpgsql;


COMMIT;


