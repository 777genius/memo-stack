# Memory Platform

Reusable memory platform for coding agents, interview assistants and future team/project memory workflows.

This project is the new source of truth for the memory platform architecture and implementation plan.

## Current Status

Docs extracted from HackInterview on 2026-05-24.

Implementation target:

```text
Memory Core Lite = Postgres canonical truth + Qdrant RAG + thin Graphiti adapter + compatibility gateway
```

Core principles:

- Clean Architecture;
- SOLID;
- simple DDD;
- port/adapter boundaries;
- Postgres as canonical truth;
- Qdrant and Graphiti as derived indexes;
- prompt memory is evidence, never instruction.

## Docs

- [Core Lite implementation plan](docs/memory-platform-core-lite-plan.md)
- [Global architecture plan](docs/memory-platform-architecture-plan.md)
- [HackInterview current memory notes](docs/hackinterview/interview-memory-clean-architecture-plan.md)
- [HackInterview integration run notes](docs/hackinterview/current-integration-run-notes.md)

## Intended Package Layout

```text
packages/
  memory_core/
  memory_server/
  memory_adapters/
  memory_sdk/

tests/
  unit/
  integration/
  e2e/
  fixtures/
```

HackInterview should consume this project through HTTP or SDK, not by importing provider-specific adapters.

## Current Implementation

Core Lite is implemented as a reusable service/library baseline:

- `memory_core` owns domain entities, application use cases and ports only;
- `memory_server` owns FastAPI routes, composition root, auth, config, admin CLI, worker CLI and eval CLI;
- `memory_adapters` owns Postgres, optional Qdrant/OpenAI/Graphiti adapters and disabled noop adapters;
- `memory_sdk` owns HTTP client calls and typed error handling for other apps;
- Postgres is canonical truth for spaces, profiles, facts, source refs, fact versions, episodes, documents, chunks, suggestions, outbox and idempotency;
- Qdrant vectors and Graphiti graph memory are derived projections behind ports;
- Qdrant adapter creates its collection on first upsert/search when enabled;
- Graphiti adapter is optional and requires Neo4j credentials when enabled;
- context/search hydrate graph/vector candidates through Postgres before rendering;
- prompt memory is rendered as evidence, never as instructions.
- prompt context is grouped by profile id and caps chunk evidence per source so
  one long document cannot consume the whole memory block;
- document/chunk classification is enforced in the prompt path: `restricted`
  memory is stored canonically but excluded from context by default, and
  `unknown` documents are not embedded until reclassified.

Implemented API surface:

- `/v1/health`, `/v1/capabilities`;
- `/v1/spaces`, `/v1/profiles`;
- `/v1/facts` remember/list/get/versions/update/forget;
- `/v1/documents` ingest/get/chunks/process/delete;
- `/v1/episodes` transcript/event ingest for HackInterview-style sessions;
- `/v1/search`, `/v1/context`;
- `/v1/thread-memory/status`, `/v1/thread-memory` delete for thread-scoped cleanup;
- `/v1/suggestions` create/list/approve/reject/expire for review-gated memory;
- `/v1/diagnostics/adapters`, `/outbox`, `/profile/{profile_id}` with production-safe metadata only;
- HackInterview-compatible `/api/v1/interview-memory/ingest`, `/context`, session status and delete routes.

Operational pieces:

- transactional outbox for derived graph/vector side effects;
- outbox worker that re-reads canonical rows and handles disabled adapters safely;
- idempotency keys are scoped by operation and profile/thread boundary, so
  client-provided retry keys cannot collide across memory profiles;
- admin commands for doctor, invariant check, projection repair dry-run and dead-job replay;
- admin service-token create/list/revoke stores token hashes only; raw token is printed once on creation;
- database service tokens support expiry and last-used tracking without storing raw tokens;
- `memory_server.db upgrade`, `admin seed-defaults` and guarded `admin reset-local`;
- schema upgrade is additive for Core Lite local databases and repairs missing
  fact/document/chunk classification columns without dropping canonical data;
- document delete hides chunks immediately and also deletes active facts whose
  current evidence only points to the deleted document or its chunks;
- redacted profile export removes fact/chunk text and source quote previews;
- small golden eval for prompt-impacting context behavior;
- import-boundary, API, worker, SDK and review-gated suggestion tests.

## Local Run

Install once:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,qdrant,openai,graphiti,mcp]'
```

The Docker compose file has two practical profiles:

```text
lite           Postgres + Memory Server, provider adapters disabled.
full           Postgres + Qdrant + Neo4j + Memory Server + worker, with OpenAI embeddings and Graphiti enabled.
```

Recommended local MVP:

```bash
make memory-stack-up-lite
make memory-smoke
make memory-mcp-smoke
```

Full provider mode needs OpenAI for embeddings and Graphiti. Do not paste the
key into commands that will be saved in shell history. Read it silently or use
an ignored local env file:

```bash
read -s OPENAI_API_KEY
export OPENAI_API_KEY
export MEMORY_OPENAI_API_KEY="$OPENAI_API_KEY"
make memory-stack-up-full
make memory-stack-smoke-full
```

`MEMORY_OPENAI_API_KEY` is used by the Memory Platform embeddings adapter.
`OPENAI_API_KEY` is also required because Graphiti reads the standard OpenAI
environment variable internally.

For a fully isolated paid canary, use a fresh Compose project and temporary
Docker volumes. The script starts isolated Postgres, Qdrant and Neo4j, runs
migrations, seeds defaults, starts the server, verifies Graphiti/Qdrant/OpenAI
behavior, then tears everything down:

```bash
make memory-clean-full-smoke
```

For local defaults, copy `.env.example` to `.env` and adjust non-secret provider
flags. Secrets should stay in your shell, `.env.local`, `.env.full`, or another
ignored file. Cognee is available as an optional adapter boundary, but the MVP
RAG path is Qdrant directly and the MVP temporal fact path is Graphiti directly.

Common local targets are available in `Makefile`, for example `make memory-lint`,
`make memory-test-unit`, `make memory-eval`, `make memory-db-upgrade`,
`make memory-seed-defaults`, `make memory-doctor`, `make memory-up`,
`make memory-server`, `make memory-stack-up-lite`, `make memory-stack-up-full`,
`make memory-clean-full-smoke` and `make memory-mcp-smoke`.

Policy modes:

```text
MEMORY_POLICY_MODE=disabled       # no server writes or retrieval
MEMORY_POLICY_MODE=manual_only    # explicit API writes, retrieval for reviewed/manual memory
MEMORY_POLICY_MODE=suggestions    # review-gated memory mode
MEMORY_POLICY_MODE=active_context # default HackInterview-compatible context mode
```

Data classification:

```text
public      # embeddable and renderable evidence
internal    # embeddable and renderable evidence
unknown     # canonical storage and keyword recall, no embeddings by default
restricted  # canonical storage only, excluded from context by default
```

Worker and operational commands:

```bash
MEMORY_SERVICE_TOKEN=local-dev-token .venv/bin/python -m memory_server.worker --once
MEMORY_SERVICE_TOKEN=local-dev-token .venv/bin/python -m memory_server.doctor
MEMORY_SERVICE_TOKEN=local-dev-token .venv/bin/python -m memory_server.admin repair-projections --space hackinterview --profile default --dry-run
MEMORY_SERVICE_TOKEN=local-dev-token .venv/bin/python -m memory_server.admin import-profile --space hackinterview --profile default --file profile-export.json --dry-run
MEMORY_SERVICE_TOKEN=local-dev-token .venv/bin/python -m memory_server.eval run --suite small-golden
```

Service tokens:

```bash
MEMORY_SERVICE_TOKEN=root-token .venv/bin/python -m memory_server.admin token create --description app
MEMORY_SERVICE_TOKEN=root-token .venv/bin/python -m memory_server.admin token create --space space_hackinterview --description hackinterview --expires-at 2026-12-31T23:59:59+00:00
MEMORY_SERVICE_TOKEN=root-token .venv/bin/python -m memory_server.admin token create --space space_hackinterview --profile profile_default --description hackinterview-default
MEMORY_SERVICE_TOKEN=root-token .venv/bin/python -m memory_server.admin token list
MEMORY_SERVICE_TOKEN=root-token .venv/bin/python -m memory_server.admin token revoke --token-id tok_...
```

The static `MEMORY_SERVICE_TOKEN` is a root token. Database service tokens are
stored as hashes only. A token created with `--space` is scoped to that space
id or slug and cannot access another space or unscoped diagnostics/list routes.
Add repeatable `--profile` values to restrict a token to specific profile ids
or external refs inside the allowed space.
Expired or revoked database tokens are rejected immediately. Token list output
contains ids, descriptions, scope, timestamps and status, never raw token values.

Graphiti local enablement requires Graphiti runtime dependencies plus Neo4j:

```bash
MEMORY_GRAPHITI_ENABLED=true \
MEMORY_GRAPHITI_NEO4J_URI=bolt://127.0.0.1:7687 \
MEMORY_GRAPHITI_NEO4J_USER=neo4j \
MEMORY_GRAPHITI_NEO4J_PASSWORD=<password> \
MEMORY_GRAPHITI_BUILD_INDICES=true \
MEMORY_SERVICE_TOKEN=local-dev-token \
.venv/bin/python -m memory_server.main
```

HackInterview local canary can point at this server:

```bash
INTERVIEW_MEMORY_API_URL=http://127.0.0.1:7788 \
INTERVIEW_MEMORY_API_VARIANT=platform \
INTERVIEW_MEMORY_AUTH_TOKEN=local-dev-token \
pnpm e2e:memory-canary -- --api-url http://127.0.0.1:7788 --auth-token local-dev-token
```

Other apps can use canonical ids or external scope refs. External refs are the
recommended integration shape for app sessions because the server resolves them
to canonical `space_id/profile_id/thread_id` behind the API boundary:

```bash
curl -X POST http://127.0.0.1:7788/v1/episodes \
  -H "Authorization: Bearer local-dev-token" \
  -H "Content-Type: application/json" \
  -d '{
    "space_slug": "hackinterview",
    "profile_external_ref": "default",
    "thread_external_ref": "session-123",
    "source_type": "system_audio",
    "source_external_id": "event-123",
    "text": "Candidate prefers FIFO queue for event processing.",
    "idempotency_key": "event-123"
  }'

curl -X POST http://127.0.0.1:7788/v1/context \
  -H "Authorization: Bearer local-dev-token" \
  -H "Content-Type: application/json" \
  -d '{
    "space_slug": "hackinterview",
    "profile_external_ref": "default",
    "thread_external_ref": "session-123",
    "query": "What did the candidate prefer for event processing?",
    "token_budget": 512
  }'
```

SDK example:

```python
from memory_sdk import MemoryPlatformClient

client = MemoryPlatformClient(token="local-dev-token")
client.remember_fact(
    space_id="space_hackinterview",
    profile_id="profile_default",
    text="Postgres is canonical truth.",
    kind="architecture_decision",
    source_refs=[{"source_type": "manual", "source_id": "note-1"}],
)

client.ingest_episode(
    space_slug="hackinterview",
    profile_external_ref="default",
    thread_external_ref="session-123",
    source_type="system_audio",
    source_external_id="event-123",
    text="Candidate prefers FIFO queue for event processing.",
    idempotency_key="event-123",
)

context = client.build_context(
    space_slug="hackinterview",
    profile_external_ref="default",
    thread_external_ref="session-123",
    query="event processing preference",
    token_budget=512,
)

suggestion = client.create_suggestion(
    space_id="space_hackinterview",
    profile_id="profile_default",
    candidate_text="Qdrant is a derived index.",
    kind="architecture_decision",
    safe_reason="review_required",
    source_refs=[{"source_type": "manual", "source_id": "note-2"}],
)
client.approve_suggestion(suggestion["data"]["id"], reason="reviewed")
```

## Local Verification

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/ruff check .
.venv/bin/python -m pytest
.venv/bin/python -m memory_server.eval run --suite small-golden
```
