# ADR-0001 - Memory Core Lite Boundaries

## Context

Memo Stack starts as Core Lite: a reusable Python service/library that Client App can consume without importing storage or provider SDKs.

## Decision

Keep `memory_core` free of FastAPI, SQLAlchemy, Qdrant, Graphiti, OpenAI and Client App imports.

Dependency direction:

```text
memory_core.domain -> stdlib only
memory_core.application -> domain + ports
memory_core.ports -> protocols and DTO contracts
memory_adapters -> memory_core ports + provider SDKs later
memory_server -> FastAPI, config and composition root
memory_sdk -> HTTP client only later
```

## Consequences

- Provider changes are adapter changes, not use case rewrites.
- Tests can enforce import boundaries from PR 0.
- Early server behavior is intentionally small: health and capabilities only.
