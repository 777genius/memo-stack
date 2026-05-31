# Memory Platform Docs

This folder contains the platform planning documents moved out of HackInterview.

## Reading Order

1. [Core Lite implementation plan](memory-platform-core-lite-plan.md)
2. [Global architecture plan](memory-platform-architecture-plan.md)
3. [MCP memory foundation plan](mcp-memory-foundation-plan.md)
4. [HackInterview current memory notes](hackinterview/interview-memory-clean-architecture-plan.md)
5. [HackInterview integration run notes](hackinterview/current-integration-run-notes.md)

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

HackInterview should keep only integration notes and pointers to this project.

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
```

Default local values:

```text
MEMORY_SMOKE_API_URL=http://127.0.0.1:7788
MEMORY_SMOKE_AUTH_TOKEN=local-dev-token
```

The smoke script uses only the public SDK and verifies the Phase 7 path:
health, space/profile creation, remember, update, document ingest, search,
context and forget.

The MCP smoke starts a real stdio MCP client and verifies status, search,
remember, update and forget through MCP tools. `memory_server` runs database
upgrade and `seed-defaults` during Docker startup. The Compose file waits for
Postgres health before starting the server and exposes a server healthcheck on
`/v1/health`.
