-- 001_dnc_schema_hardening.sql
-- Purpose: Strengthen DNC workflow schema with tracking fields, FKs, and indexes
-- Notes: Pure PostgreSQL DDL. Safe to re-run (IF EXISTS/IF NOT EXISTS used where possible).

BEGIN;

-- =============================
-- dnc_requests
-- =============================
-- Ensure core lifecycle timestamps and actor tracking exist
ALTER TABLE IF EXISTS dnc_requests
  ADD COLUMN IF NOT EXISTS submitted_at           timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS approved_at            timestamptz,
  ADD COLUMN IF NOT EXISTS rejected_at            timestamptz,
  ADD COLUMN IF NOT EXISTS propagation_started_at timestamptz,
  ADD COLUMN IF NOT EXISTS propagation_completed_at timestamptz,
  ADD COLUMN IF NOT EXISTS completed_at           timestamptz,
  ADD COLUMN IF NOT EXISTS decision_notes         text,
  ADD COLUMN IF NOT EXISTS reviewed_by_user_id    integer,
  ADD COLUMN IF NOT EXISTS last_updated_at        timestamptz DEFAULT now();

-- Status discipline
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM   pg_constraint
    WHERE  conname = 'ck_dnc_requests_status_valid'
  ) THEN
    ALTER TABLE dnc_requests
      ADD CONSTRAINT ck_dnc_requests_status_valid
      CHECK (status IN ('pending','approved','denied','propagating','completed','cancelled'));
  END IF;
END$$;

-- Foreign keys (ignore errors if referenced tables don’t exist in this env)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints 
    WHERE constraint_name = 'fk_dnc_requests_reviewed_by_user'
  ) THEN
    ALTER TABLE dnc_requests
      ADD CONSTRAINT fk_dnc_requests_reviewed_by_user
      FOREIGN KEY (reviewed_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints 
    WHERE constraint_name = 'fk_dnc_requests_requested_by_user'
  ) THEN
    ALTER TABLE dnc_requests
      ADD CONSTRAINT fk_dnc_requests_requested_by_user
      FOREIGN KEY (requested_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints 
    WHERE constraint_name = 'fk_dnc_requests_org'
  ) THEN
    ALTER TABLE dnc_requests
      ADD CONSTRAINT fk_dnc_requests_org
      FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;
  END IF;
END$$;

-- Indexes for common filters and lookups
CREATE INDEX IF NOT EXISTS idx_dnc_requests_status             ON dnc_requests(status);
CREATE INDEX IF NOT EXISTS idx_dnc_requests_org_phone          ON dnc_requests(organization_id, phone_e164);
CREATE INDEX IF NOT EXISTS idx_dnc_requests_org_status_created ON dnc_requests(organization_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_dnc_requests_decided_at_desc    ON dnc_requests(decided_at DESC);


-- =============================
-- dnc_entries
-- =============================
ALTER TABLE IF EXISTS dnc_entries
  ADD COLUMN IF NOT EXISTS active              boolean    DEFAULT true NOT NULL,
  ADD COLUMN IF NOT EXISTS created_at          timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at          timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS removed_at          timestamptz,
  ADD COLUMN IF NOT EXISTS created_by_user_id  integer,
  ADD COLUMN IF NOT EXISTS request_id          integer,
  ADD COLUMN IF NOT EXISTS source              text,
  ADD COLUMN IF NOT EXISTS notes               text;

-- Uniqueness by org + phone
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'uq_dnc_entries_org_phone'
  ) THEN
    -- Create unique index via constraint name for clarity
    ALTER TABLE dnc_entries
      ADD CONSTRAINT uq_dnc_entries_org_phone UNIQUE (organization_id, phone_e164);
  END IF;
END$$;

-- FKs
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints WHERE constraint_name = 'fk_dnc_entries_created_by_user'
  ) THEN
    ALTER TABLE dnc_entries
      ADD CONSTRAINT fk_dnc_entries_created_by_user
      FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints WHERE constraint_name = 'fk_dnc_entries_request'
  ) THEN
    ALTER TABLE dnc_entries
      ADD CONSTRAINT fk_dnc_entries_request
      FOREIGN KEY (request_id) REFERENCES dnc_requests(id) ON DELETE SET NULL;
  END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_dnc_entries_org_phone ON dnc_entries(organization_id, phone_e164);


-- =============================
-- propagation_attempts
-- =============================
ALTER TABLE IF EXISTS propagation_attempts
  ADD COLUMN IF NOT EXISTS request_id         integer,
  ADD COLUMN IF NOT EXISTS http_status        integer,
  ADD COLUMN IF NOT EXISTS provider_request_id text,
  ADD COLUMN IF NOT EXISTS response_payload   jsonb,
  ADD COLUMN IF NOT EXISTS error_message      text,
  ADD COLUMN IF NOT EXISTS created_at         timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS started_at         timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS finished_at        timestamptz,
  ADD COLUMN IF NOT EXISTS attempt_no         integer    DEFAULT 1,
  ADD COLUMN IF NOT EXISTS status             text       DEFAULT 'pending';

-- Status discipline
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ck_propagation_attempts_status_valid'
  ) THEN
    ALTER TABLE propagation_attempts
      ADD CONSTRAINT ck_propagation_attempts_status_valid
      CHECK (status IN ('pending','in_progress','success','failed'));
  END IF;
END$$;

-- FKs
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints WHERE constraint_name = 'fk_attempts_request'
  ) THEN
    ALTER TABLE propagation_attempts
      ADD CONSTRAINT fk_attempts_request
      FOREIGN KEY (request_id) REFERENCES dnc_requests(id) ON DELETE SET NULL;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints WHERE constraint_name = 'fk_attempts_org'
  ) THEN
    ALTER TABLE propagation_attempts
      ADD CONSTRAINT fk_attempts_org
      FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;
  END IF;
END$$;

-- Indexes for admin monitor and background workers
CREATE INDEX IF NOT EXISTS idx_attempts_started_at_desc        ON propagation_attempts(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_attempts_req                    ON propagation_attempts(request_id);
CREATE INDEX IF NOT EXISTS idx_attempts_org_service_status     ON propagation_attempts(organization_id, service_key, status);
CREATE INDEX IF NOT EXISTS idx_attempts_org_phone_provider     ON propagation_attempts(organization_id, phone_e164, service_key);


-- =============================
-- Generic updated_at triggers
-- =============================
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_dnc_entries_set_updated_at'
  ) THEN
    CREATE TRIGGER trg_dnc_entries_set_updated_at
    BEFORE UPDATE ON dnc_entries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
END$$;

-- Maintain last_updated_at on dnc_requests
CREATE OR REPLACE FUNCTION set_last_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.last_updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_dnc_requests_set_last_updated'
  ) THEN
    CREATE TRIGGER trg_dnc_requests_set_last_updated
    BEFORE UPDATE ON dnc_requests
    FOR EACH ROW EXECUTE FUNCTION set_last_updated_at();
  END IF;
END$$;

COMMIT;


