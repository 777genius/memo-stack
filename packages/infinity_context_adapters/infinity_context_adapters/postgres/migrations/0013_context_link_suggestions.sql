CREATE TABLE IF NOT EXISTS memory_context_link_suggestions (
    id VARCHAR(80) PRIMARY KEY,
    space_id VARCHAR(80) NOT NULL,
    memory_scope_id VARCHAR(80) NOT NULL,
    source_type VARCHAR(80) NOT NULL,
    source_id VARCHAR(160) NOT NULL,
    target_type VARCHAR(80) NOT NULL,
    target_id VARCHAR(160) NOT NULL,
    relation_type VARCHAR(80) NOT NULL,
    confidence VARCHAR(40) NOT NULL DEFAULT 'medium',
    reason VARCHAR(320) NOT NULL,
    score DOUBLE PRECISION NOT NULL DEFAULT 0,
    status VARCHAR(40) NOT NULL DEFAULT 'pending',
    metadata_json JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    reviewed_at TIMESTAMPTZ,
    review_reason VARCHAR(320)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_context_link_suggestion_pending
ON memory_context_link_suggestions(
    space_id,
    memory_scope_id,
    source_type,
    source_id,
    target_type,
    target_id,
    relation_type
)
WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS ix_context_link_suggestions_source
ON memory_context_link_suggestions(
    space_id,
    memory_scope_id,
    source_type,
    source_id,
    status,
    updated_at
);

CREATE INDEX IF NOT EXISTS ix_context_link_suggestions_status
ON memory_context_link_suggestions(space_id, memory_scope_id, status, updated_at);
