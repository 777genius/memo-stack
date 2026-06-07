ALTER TABLE memory_facts
  ADD COLUMN IF NOT EXISTS category VARCHAR(80);

ALTER TABLE memory_facts
  ADD COLUMN IF NOT EXISTS tags_json JSON NOT NULL DEFAULT '[]';

ALTER TABLE memory_facts
  ADD COLUMN IF NOT EXISTS ttl_policy VARCHAR(80);

ALTER TABLE memory_facts
  ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS ix_memory_facts_taxonomy
  ON memory_facts (space_id, profile_id, category, status);
