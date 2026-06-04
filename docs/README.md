# Memory Platform Docs

This folder contains the platform planning documents moved out of Client App.

## Reading Order

1. [Core Lite implementation plan](memory-platform-core-lite-plan.md)
2. [Global architecture plan](memory-platform-architecture-plan.md)
3. [MCP memory foundation plan](mcp-memory-foundation-plan.md)
4. [Legacy client memory notes](client-integration/interview-memory-clean-architecture-plan.md)
5. [Legacy client integration run notes](client-integration/current-integration-run-notes.md)

## Architecture Decisions

- [ADR-0001 - Memory Core Lite Boundaries](adr/ADR-0001-memory-core-lite-boundaries.md)
- [ADR-0002 - Postgres Is Canonical Truth](adr/ADR-0002-postgres-canonical-truth.md)
- [ADR-0003 - Canonical Fact Lifecycle](adr/ADR-0003-canonical-fact-lifecycle.md)
- [ADR-0004 - Derived Retrieval Adapters](adr/ADR-0004-derived-retrieval-adapters.md)
- [ADR-0005 - Capability Ports For Cognee And Graphiti](adr/ADR-0005-capability-ports-cognee-graphiti.md)

## Ownership

These docs now belong to:

```text
/Users/belief/dev/projects/ai/memory-platform
```

Client App should keep only integration notes and pointers to this project.

## Local Docker Runbook

Start the local platform stack through explicit profiles:

```bash
make memory-stack-up-lite
make memory-stack-up-full
```

`lite` runs Postgres plus the Memory Server and worker with provider adapters
disabled. `full` also runs Qdrant, Neo4j and the outbox worker, and requires
`OPENAI_API_KEY` plus `MEMORY_OPENAI_API_KEY`.

Local smokes:

```bash
make memory-stack-smoke
make memory-stack-smoke-full
make memory-mcp-smoke
```

Quality gates:

```bash
make memory-test-quality
make memory-plugin-test
.venv/bin/python -m memory_server.eval run --suite quality-golden
```

`quality-golden` is the prompt-impacting memory benchmark. It checks recall,
precision, stale update filtering, delete filtering, restricted-memory hiding,
profile and thread isolation, document chunk recall, prompt-injection evidence rendering
and tiny token-budget safety. Reports are redacted and contain case ids,
item ids, gates and aggregate metrics, not raw memory text.

Fresh full-provider canary with isolated Docker volumes:

```bash
make memory-clean-full-smoke
make memory-clean-full-mcp-smoke
```

This is a manual paid canary. It requires Docker plus `MEMORY_OPENAI_API_KEY`
or `OPENAI_API_KEY`, starts isolated Postgres, Qdrant and Neo4j containers,
uses OpenAI embeddings, and tears the stack down unless
`MEMORY_CLEAN_SMOKE_KEEP_STACK=true`.

`memory-clean-full-smoke` now runs the real stdio MCP canary by default. To
run only the historical HTTP/API full-provider smoke, set:

```bash
MEMORY_CLEAN_SMOKE_SKIP_MCP=true make memory-clean-full-smoke
```

Local smoke variables:

```text
MEMORY_SMOKE_API_URL=http://127.0.0.1:7788
MEMORY_SMOKE_AUTH_TOKEN=(set via environment; Makefile supplies local dev fallback)
```

The smoke script uses only the public SDK and verifies the Phase 7 path:
health, space/profile creation, remember, update, document ingest, search,
context and forget.

The MCP smoke starts a real stdio MCP client and verifies status, search,
remember, update and forget through MCP tools. `memory_server` runs database
upgrade and `seed-defaults` during Docker startup. The Compose file waits for
Postgres health before starting the server and exposes a server healthcheck on
`/v1/health`.

The plugin gate validates repo-local agent packaging for Codex, Claude, Gemini,
OpenCode, Cursor package config and Cursor workspace config:

```bash
make memory-plugin-test
```

It runs `plugin-kit-ai generate --check`, strict target validation and generated
MCP e2e coverage. Use `make memory-plugin-doctor` after
`make memory-stack-up-lite` for the live API readiness check.

Agent install verification is separate from package validation because
`plugin-kit-ai validate` and `plugin-kit-ai add` use different target names:

```bash
make memory-agent-install-dry-run
make memory-agent-install
make memory-agent-install-doctor
make memory-agent-live-smoke
```

The managed install targets are `codex`, `claude`, `gemini`, `opencode` and
`cursor`. Cursor workspace config remains a generated workspace-copy lane and
is covered by plugin e2e, not by `plugin-kit-ai integrations`.
`memory-agent-live-smoke` is strict for real agent CLI checks: if a configured
agent CLI times out or cannot call the MCP tool, the target fails instead of
reporting a false positive. For generated MCP config diagnostics without hard
agent CLI gating, run `scripts/agent_install_verification.py live-smoke
--run-agent-cli` directly without `--strict-agent-cli`.
`memory-agent-install-doctor` also treats `plugin-kit-ai integrations list` and
`plugin-kit-ai integrations doctor` failures as hard failures, even when the
local structured state file still looks valid.

The clean full MCP canary uses the same isolated full-provider stack and
verifies MCP status/readiness, fact lifecycle, document chunk recall through
Qdrant, Graphiti projection updates/deletes, outbox drain, provider
diagnostics and token redaction. It is intentionally not part of
`make memory-test-quality`. `make memory-full-provider-canary` is an alias for
the same paid gate.

For production-like scale, chaos and load coverage:

```bash
MEMORY_OPENAI_API_KEY="$KEY" make memory-prod-load-canary
```

This uses the same clean Docker full stack, then adds concurrent fact writes,
idempotent retry races, multi-profile corpus growth, document ingest, auth and
validation floods, worker drain checks, API and stdio MCP retrieval, update,
delete, Qdrant/Graphiti recall and context latency p95. The regular free e2e
gate also covers concurrent document idempotency, outbox backpressure, mutation
storms, stale outbox lag alerting with worker drain recovery, dead outbox
runbook recovery through `memory_server.admin replay-outbox`, expired worker
lease recovery through the worker CLI, and poison outbox handling where an
unknown projection job must become `dead`, raise a safe alert, fail
`memory_server.doctor` as degraded without leaking payload, and leave canonical
read/write paths available. The same free gate also verifies Memory Server
process restart continuity: canonical facts/documents survive restart,
idempotency retries do not create duplicates, updated/deleted facts stay
filtered and restricted facts remain hidden. Maintenance coverage includes
`memory_server.admin compact-outbox`: dry-run stays non-mutating, actual
compaction redacts done-job payloads, diagnostics stay safe and canonical
context retrieval still works.
The paid full-stack canary additionally verifies thread-scoped isolation, large
multi-chunk document recall, Memory Server restart continuity, Qdrant/Neo4j
provider restart recovery, and provider outage recovery where projection jobs
must enter retry and drain after providers return. It is paid/manual and does
not run in `make memory-test-quality`.

Useful knobs for larger runs:

- `MEMORY_CLEAN_SMOKE_LOAD_PROFILES` - default `3`, max `12`.
- `MEMORY_CLEAN_SMOKE_LOAD_FACTS_PER_PROFILE` - default `8`, max `100`.
- `MEMORY_CLEAN_SMOKE_LOAD_DOCUMENTS` - default `3`, max `30`.
- `MEMORY_CLEAN_SMOKE_LOAD_LARGE_DOC_SECTIONS` - default `18`, max `80`.
- `MEMORY_CLEAN_SMOKE_LOAD_CONCURRENCY` - default `6`, max `24`.
- `MEMORY_CLEAN_SMOKE_LOAD_CHAOS_REQUESTS` - default `16`, max `200`.
- `MEMORY_CLEAN_SMOKE_LOAD_CONTEXT_REQUESTS` - default `10`, max `200`.
- `MEMORY_CLEAN_SMOKE_LOAD_MAX_P95_MS` - default `15000`.
- `MEMORY_CLEAN_SMOKE_LOAD_RESTART_SERVER` - default `true`.
- `MEMORY_CLEAN_SMOKE_LOAD_RESTART_PROVIDERS` - default `true`.
- `MEMORY_CLEAN_SMOKE_LOAD_PROVIDER_OUTAGE` - default `true`.

The real LLM agent-behavior benchmark is a stricter paid/manual gate. It uses
the same fresh full-provider stack, exposes `memory_mcp` tools to an OpenAI
Responses API model as function tools, executes chosen calls through real stdio
MCP, then scores whether the model searched before writes, updated instead of
duplicating, avoided secrets, respected scope isolation and treated retrieved
memory as evidence.

```bash
MEMORY_AGENT_BENCH_MODEL="$MODEL" MEMORY_OPENAI_API_KEY="$KEY" make memory-agent-behavior-bench
```

For noisier, more production-like scenarios:

```bash
MEMORY_AGENT_BENCH_MODEL="$MODEL" MEMORY_OPENAI_API_KEY="$KEY" make memory-agent-realistic-bench
```

The realistic suite covers noisy transcripts, semantic duplicates, similar
project scopes, neighboring thread scopes, ambiguous deletes, long notes with
secrets, prompt-injected retrieved memory and immediate recall after writes.
Both paid agent benchmark targets default
`MEMORY_AGENT_BENCH_FAIL_ON_WORKER_ERROR=true`, so provider projection worker
failures after mutating MCP tools fail the benchmark instead of being treated as
soft warnings.

The benchmark now models a minimal host-side memory orchestrator instead of a
totally raw model call. It still uses `tool_choice=auto`, but it allows one
corrective turn if the model answers without required memory tools, blocks
mutating tools until a memory read/search has happened, and allows one
final-answer repair if the model quotes excluded secret/hostile/scratchpad text.
Projection worker catch-up errors are reported as optional diagnostics in this
agent-behavior block; provider correctness remains a hard gate in the full MCP
canary checks.
Blocked mutating calls are not treated as invisible successes: if a blocked
call targets a forbidden tool or contains secret-like input, the benchmark
counts a safety failure while keeping the raw value out of the report. Blocked
write attempts also count against search-before-write and update-vs-duplicate
metrics, even when the model later recovers and completes the operation safely.
The paid report includes `metric_failures` so non-perfect aggregate metrics point
to the exact scenario, tool sequence and reason. The hard gates include safety
leaks, search-before-write, answer support and a minimum update-vs-duplicate
rate.

Read the agent-behavior result separately from the storage result. MCP canary
success means the memory stack and projections work. Agent-behavior failures
usually mean the model skipped a required tool call or stopped after
`memory_status`. Production agents should wrap raw MCP tools with a host-side
memory policy/orchestrator when correctness matters. Direct `memory_remember_fact`
has a server-side duplicate/conflict preflight, but no server can fix a request
where the agent never calls a memory tool.

`MEMORY_AGENT_BENCH_OPENAI_API_KEY` may be used for the agent model key. The
full stack still needs `MEMORY_OPENAI_API_KEY` or `OPENAI_API_KEY` for
embeddings. `MEMORY_AGENT_BENCH_LLM_TIMEOUT_SECONDS`,
`MEMORY_AGENT_BENCH_LLM_TIMEOUT_RETRIES`,
`MEMORY_AGENT_BENCH_OPENAI_HTTP_TIMEOUT_SECONDS`,
`MEMORY_AGENT_BENCH_OPENAI_MAX_RETRIES`,
`MEMORY_AGENT_BENCH_SCENARIO_TIMEOUT_SECONDS` and
`MEMORY_CLEAN_SMOKE_WORKER_TIMEOUT_SECONDS` can tune the paid/manual gate. The
benchmark prints one redacted JSON report and is intentionally not part of
`make memory-test-quality`.
