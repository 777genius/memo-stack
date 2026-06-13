CREATE TABLE IF NOT EXISTS memory_asset_extraction_jobs (
    id VARCHAR(80) PRIMARY KEY,
    asset_id VARCHAR(80) NOT NULL,
    space_id VARCHAR(80) NOT NULL,
    memory_scope_id VARCHAR(80) NOT NULL,
    thread_id VARCHAR(80),
    parser_profile VARCHAR(80) NOT NULL,
    parser_config_hash VARCHAR(80) NOT NULL,
    source_sha256_hex VARCHAR(80) NOT NULL,
    parser_name VARCHAR(120),
    parser_version VARCHAR(120),
    model_version VARCHAR(120),
    status VARCHAR(40) NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    safe_error_code VARCHAR(120),
    safe_error_message VARCHAR(500),
    result_document_ids_json JSON NOT NULL DEFAULT '[]',
    metadata_json JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_asset_extraction_jobs_asset_status
ON memory_asset_extraction_jobs(asset_id, status, created_at);

CREATE INDEX IF NOT EXISTS ix_asset_extraction_jobs_scope_status
ON memory_asset_extraction_jobs(space_id, memory_scope_id, status, updated_at);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asset_extraction_jobs_active_profile
ON memory_asset_extraction_jobs(
    asset_id,
    parser_profile,
    parser_config_hash,
    source_sha256_hex
)
WHERE status IN ('pending', 'running', 'succeeded');

CREATE TABLE IF NOT EXISTS memory_asset_extraction_artifacts (
    id VARCHAR(80) PRIMARY KEY,
    job_id VARCHAR(80) NOT NULL,
    asset_id VARCHAR(80) NOT NULL,
    artifact_type VARCHAR(80) NOT NULL,
    storage_backend VARCHAR(80) NOT NULL,
    storage_key VARCHAR(500) NOT NULL,
    sha256_hex VARCHAR(80) NOT NULL,
    byte_size INTEGER NOT NULL,
    metadata_json JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_asset_extraction_artifacts_job
ON memory_asset_extraction_artifacts(job_id, artifact_type);

CREATE INDEX IF NOT EXISTS ix_asset_extraction_artifacts_asset
ON memory_asset_extraction_artifacts(asset_id, created_at);
