CREATE TABLE IF NOT EXISTS memory_usage_records (
    id VARCHAR(80) PRIMARY KEY,
    subject_type VARCHAR(40) NOT NULL,
    subject_id VARCHAR(80) NOT NULL,
    space_id VARCHAR(80) NOT NULL,
    memory_scope_id VARCHAR(80),
    resource VARCHAR(80) NOT NULL,
    quantity INTEGER NOT NULL,
    status VARCHAR(40) NOT NULL,
    source_type VARCHAR(80) NOT NULL,
    source_id VARCHAR(120) NOT NULL,
    idempotency_key VARCHAR(240) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    metadata_json JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_memory_usage_idempotency
ON memory_usage_records(idempotency_key);

CREATE INDEX IF NOT EXISTS ix_memory_usage_subject_window
ON memory_usage_records(
    subject_type,
    subject_id,
    resource,
    status,
    window_start,
    window_end
);

CREATE INDEX IF NOT EXISTS ix_memory_usage_space_created
ON memory_usage_records(space_id, created_at);
