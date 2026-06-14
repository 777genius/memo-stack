ALTER TABLE memory_asset_extraction_jobs
ADD COLUMN IF NOT EXISTS lease_owner VARCHAR(120);

ALTER TABLE memory_asset_extraction_jobs
ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ;

ALTER TABLE memory_asset_extraction_jobs
ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ;

ALTER TABLE memory_asset_extraction_jobs
ADD COLUMN IF NOT EXISTS retry_after_at TIMESTAMPTZ;

ALTER TABLE memory_asset_extraction_jobs
ADD COLUMN IF NOT EXISTS cancellation_requested_at TIMESTAMPTZ;

ALTER TABLE memory_asset_extraction_jobs
ADD COLUMN IF NOT EXISTS retry_disposition VARCHAR(40);

CREATE INDEX IF NOT EXISTS ix_asset_extraction_jobs_running_lease
ON memory_asset_extraction_jobs(status, lease_expires_at, heartbeat_at);
