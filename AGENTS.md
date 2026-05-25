# AGENTS.md

## Project Intent

This repository is the reusable Memory Platform extracted from HackInterview planning docs.

Implement according to:

- Clean Architecture;
- SOLID;
- simple DDD;
- port/adapter boundaries;
- Postgres canonical lifecycle;
- Qdrant and Graphiti as derived indexes;
- provider dependencies isolated in adapters;
- prompt memory rendered as evidence, not instruction.

## Source Of Truth

Start with:

```text
docs/memory-platform-core-lite-plan.md
```

Global reference:

```text
docs/memory-platform-architecture-plan.md
```

HackInterview compatibility notes:

```text
docs/hackinterview/interview-memory-clean-architecture-plan.md
```

## Implementation Rule

Do not let `memory_core` import FastAPI, SQLAlchemy, Qdrant, Graphiti, OpenAI or HackInterview code.

Implementation order:

```text
domain/ports -> application use cases -> Postgres canonical lifecycle -> compatibility API -> Qdrant RAG -> context eval -> Graphiti adapter -> SDK/Docker
```
