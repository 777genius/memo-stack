# Memory Platform Critical Rules

This document is the implementation guardrail for advanced memory features:
Context Assembly v2, semantic anchors, temporal invalidation, evals, and review UX.

## Research baseline

Current competitive memory systems converge on the same core ideas:

- Multi-signal retrieval: semantic vectors, keyword/BM25-like matching, graph relations,
  recency, trust, and scope/thread locality.
- Entity-first memory: people, projects, organizations, places, and events are canonical
  anchors, not only free-form tags.
- Temporal memory: facts and relations change over time; retrieval must preserve
  provenance and avoid stale/deleted leakage.
- Evidence-first output: retrieved memory is evidence with source refs, never hidden
  instruction.
- Review gates: uncertain writes, merges, supersedence, and relation suggestions need
  clear approve/reject/edit flows.
- Continuous evals: retrieval quality, linking quality, stale-memory safety, and
  review UX regressions must be measured with golden cases.

Useful references checked during planning:

- Mem0 migration docs emphasize add-only extraction, hybrid search, and entity linking.
- Graphiti/Zep emphasize temporal context graphs, provenance, evolving facts, and
  context assembly for agents.
- Letta separates always-visible memory blocks from on-demand archival memory.
- RAG evaluation references emphasize measuring retrieval and generation separately,
  including recall, precision, faithfulness, and answer relevance.

## Non-negotiable architecture rules

1. `memo_stack_core` must not import FastAPI, SQLAlchemy, Qdrant, Graphiti, OpenAI,
   Docling, browser, Flutter, or app-specific code.
2. Postgres remains the canonical source of truth. Qdrant, Graphiti, and external
   providers are derived indexes/adapters.
3. All provider dependencies enter through ports. Provider failure must degrade or
   produce safe diagnostics instead of leaking exceptions into public API payloads.
4. Retrieval output must be evidence-only. Rendered memory must never contain hidden
   instructions or imply authority beyond source evidence.
5. Deleted, superseded, disputed, restricted, wrong-scope, or stale candidates must be
   filtered before ranking whenever they are not explicitly requested for review/debug.
6. Ranking must be explainable. Every selected context item should expose bounded,
   non-sensitive score signals and source provenance.
7. Canonical anchors must be mergeable/splittable and alias-aware. Tags can assist UI,
   but tags are not a substitute for people/events/projects/organizations.
8. Temporal behavior must be explicit. New facts or relations should support
   `observed_at`, `valid_from`, `valid_to`, `supersedes`, and `contradicts` semantics
   where the domain supports them.
9. Review UX must allow approve, reject, edit target, change relation, and inspect
   reasons/evidence. Batch operations must stay bounded and auditable.
10. Evals are product gates, not optional tests. Every risky memory behavior needs a
    golden case that can fail when relevance, safety, or provenance regresses.

## Implementation order

1. Strengthen existing `BuildContextUseCase` instead of creating a parallel retrieval
   stack.
2. Normalize ranking signals and provenance in core DTOs.
3. Promote anchors as first-class targets in retrieval and relation suggestions.
4. Add temporal relation metadata and invalidation policies.
5. Expand golden evals around retrieval, anchor linking, stale memory, and review UX.
6. Expose review UX improvements through existing API contracts before adding new UI
   screens.
