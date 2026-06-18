# ADR-0001 - Infinity Context Core Lite Boundaries

## Context

Infinity Context starts as Core Lite: a reusable Python service/library that Client App can consume without importing storage or provider SDKs.

## Decision

Keep `infinity_context_core` free of FastAPI, SQLAlchemy, Qdrant, Graphiti, OpenAI and Client App imports.

Dependency direction:

```text
infinity_context_core.domain -> stdlib only
infinity_context_core.application -> domain + ports
infinity_context_core.ports -> protocols and DTO contracts
infinity_context_adapters -> infinity_context_core ports + provider SDKs later
infinity_context_server -> FastAPI, config and composition root
infinity_context_sdk -> HTTP client only later
```

## Consequences

- Provider changes are adapter changes, not use case rewrites.
- Tests can enforce import boundaries from PR 0.
- Early server behavior is intentionally small: health and capabilities only.
