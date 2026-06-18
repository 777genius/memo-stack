ALTER TABLE memory_service_tokens
    ADD COLUMN IF NOT EXISTS memory_scope_ids_json JSONB;
