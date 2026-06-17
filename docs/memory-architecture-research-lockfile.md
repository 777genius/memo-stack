# Memory Architecture Research Lockfile

Status: locked product rules for Memo Stack memory architecture.

Date: 2026-06-18.

This file is not a brainstorming note. It is the product and architecture
lockfile for memory behavior. Any change that weakens these rules needs a new
ADR, migration notes and eval coverage.

## External Inputs Reviewed

- [Mem0 memory types](https://docs.mem0.ai/core-concepts/memory-types) and
  [Mem0 long-term memory overview](https://mem0.ai/blog/long-term-memory-ai-agents)
  separate factual, episodic and semantic memory, with procedural memory used
  for behavior and reusable workflows.
- [Zep concepts](https://help.getzep.com/concepts),
  [Zep Graph Overview](https://help.getzep.com/graph-overview) and
  [Graphiti](https://github.com/getzep/graphiti) use a temporal context graph
  where entities, facts and relationships preserve history while invalidating
  outdated facts.
- [OpenAI agent safety guidance](https://developers.openai.com/api/docs/guides/agent-builder-safety)
  and [OpenAI deep research safety guidance](https://developers.openai.com/api/docs/guides/deep-research)
  treat retrieved text, files, tool output and connector data as untrusted input
  that can contain prompt injection or exfiltration attempts.
- [OpenAI Model Spec](https://model-spec.openai.com/) recommends isolating
  untrusted data from instructions. Memo Stack applies this by rendering memory
  as evidence only.

## Locked Product Model

Memo Stack stores memory as canonical evidence plus derived retrieval indexes.
The user experience can look like quick capture, chat, project inbox or review
queue, but the storage model stays the same.

### Memory Types

Semantic memory:

- Stable facts, preferences, relationships, decisions and domain knowledge.
- Stored canonically as facts, anchors and explicit relations.
- Prompt-visible only when active, current, scoped and policy-allowed.

Episodic memory:

- Events, conversations, calls, captures, documents, screenshots, audio/video
  segments and user actions with time and source context.
- Stored as captures, episodes, assets, documents, chunks and extraction
  artifacts.
- Used as evidence for semantic suggestions, not silently converted into truth.

Procedural memory:

- Reusable workflows, policies, review decisions, user-approved behaviors and
  tool usage preferences.
- Stored separately from ordinary facts when it can affect future behavior.
- Requires explicit review before becoming active context.

Archival memory:

- Old, superseded, low-confidence or rarely used evidence kept for audit,
  search, recovery and debug.
- Hidden from default prompt context.
- Available in review/debug modes with stale/superseded/deleted reason codes.

## Canonical Anchors vs Tags

Canonical anchors are durable entities:

- People, organizations, projects, events, documents and important concepts.
- Have kind, normalized key, aliases, confidence, evidence refs, lifecycle
  status and temporal validity.
- Support merge, split, audit trail and alias conflict checks.
- Can be linked to facts, captures, assets, chunks, suggestions and threads.

Tags are lightweight facets:

- User-facing labels for filtering, grouping and quick navigation.
- May be created automatically, but never replace anchors.
- Can be wrong without corrupting the semantic graph.
- Should be editable/removable without changing fact identity.

Locked rule:

```text
Tags help users browse. Anchors help the system reason.
```

If the system needs identity, disambiguation, time validity or relations, it
must use anchors or explicit relations, not tags alone.

## Temporal Validity

Every prompt-impacting semantic item must be compatible with bitemporal-lite:

- `observed_at` records when Memo Stack learned or observed the claim.
- `valid_from` records when the claim becomes true in the user's world.
- `valid_to` records when the claim stops being true in the user's world.
- Missing `valid_from` means valid from observation time unless a stronger
  source says otherwise.
- Missing `valid_to` means still current until superseded, disputed, deleted or
  expired.

Default context retrieval:

- Shows active current facts and current relations.
- Hides superseded targets when a current active supersedes relation exists.
- Hides disputed/contradicted facts by default.
- Hides deleted, restricted and out-of-scope items.

Review/debug retrieval:

- May show stale, superseded, disputed and expired items.
- Must include reason codes and relation ids.
- Must not silently mix stale facts into normal active context.

## Review Gates

Memo Stack must prefer safe review over silent automation.

Auto-link is allowed only when all are true:

- High confidence.
- Strong relation-specific evidence.
- No active duplicate or conflict.
- No ambiguity between same-name anchors.
- No restricted source.
- No prompt-injection or instruction-like source promotion.
- Payload stays within max suggestions and diagnostic limits.

Pending review is required when any are true:

- Medium confidence.
- Multiple plausible targets.
- New anchor creation from weak evidence.
- Temporal phrase is ambiguous.
- Source is AI-generated or low trust.
- Relation can change future behavior.
- Suggested procedural memory.

Deny without suggestion when any are true:

- Score below threshold.
- Only weak lexical overlap.
- Candidate is from wrong scope/thread and not explicitly requested.
- Target is deleted/restricted.
- Candidate reason would expose secrets or raw private payload.
- No candidate is better than a hallucinated candidate.

## No Hidden Instruction Memory

Memory is evidence, not instruction.

Locked rules:

- Retrieved memory must be rendered under an evidence header.
- Memory text must never be inserted as developer/system instructions.
- Prompt injection inside documents, screenshots, audio/video transcripts or
  tool output remains quoted evidence.
- Procedural memory that can change behavior requires explicit review and a
  separate lifecycle.
- Source text can be useful while still untrusted.

## Canonical Truth And Derived Indexes

Postgres is canonical:

- Owns lifecycle, status, source refs, temporal fields, review state and audit.
- Delete/forget must hide data from context immediately through canonical
  visibility, even if derived indexes lag.
- Import/export and migrations must preserve canonical ids or remap them with
  explicit conflict reports.

Qdrant is derived:

- Stores chunk vectors for recall.
- Can be stale or unavailable without corrupting canonical truth.
- Every vector result must be rehydrated through canonical visibility.

Graphiti is derived:

- Stores temporal graph projections and graph retrieval hints.
- Cannot be the only proof that a fact, anchor or relation exists.
- Every graph result must be rehydrated through canonical visibility.

Provider adapters are replaceable:

- Provider-specific metadata stays in adapters or bounded diagnostics.
- Core use cases depend on ports, not SDKs.
- Unsupported capabilities are explicit degraded/skipped status, not fake
  success.

## Scoring And Provenance Schema

Every context item must expose bounded diagnostics with no secrets.

Required item diagnostics:

```text
retrieval_source
retrieval_sources
ranking_reason
score_signals
provenance
memory_scope_id
```

Required bundle diagnostics:

```text
context_assembly_version
consistency_mode
retrieval_sources_used
hybrid_items_used
temporal_replacements_applied
temporal_relations_skipped_by_validity
items_considered
items_used
dropped_by_budget
dropped_by_source_cap
dropped_by_char_cap
diagnostics_truncated
```

Score signals:

- Numeric or enum-like only.
- No raw query terms.
- No auth tokens, URLs with credentials, full source text or raw provider
  payloads.
- Must include enough data to explain ranking without leaking content.

Provenance:

- Source type and source id.
- Chunk/document ids when available.
- Retrieval sources.
- Source ref count.
- Temporal relation ids when temporal replacement happened.
- Sequence or character offsets for chunks when available.

Deterministic ordering:

- Primary sort is score.
- Tie-breakers must use stable source/provenance fields before generated ids.
- Random ids cannot decide which evidence fits into a capped context.

## API And SDK Contract

Public APIs and SDKs must support:

- List review suggestions with filters.
- Approve/reject with reason.
- Approve with target override.
- Bounded batch review.
- List anchors and evidence.
- Typed context diagnostics.
- No raw provider-specific payloads in public responses.

Compatibility rule:

```text
Adding fields is allowed. Removing or renaming public response fields requires
compatibility tests and migration notes.
```

## Eval Contract

Prompt-impacting changes require deterministic evals for:

- Superseded old fact hidden, new fact shown.
- Disputed/contradicted hidden by default.
- Similar project is not matched.
- Same-name person vs project disambiguation.
- Screenshot or document evidence linked to the right chunk.
- No candidate means no candidate.
- Hybrid retrieval beats single source when both are valid.
- Tail recall in long documents.
- Prompt injection remains evidence only.

Minimum gate before major memory behavior changes:

```bash
.venv/bin/python -m memo_stack_server.eval run --suite quality-golden
.venv/bin/python -m memo_stack_server.eval run --suite semantic-linking-golden
```

## Change Policy

This lockfile can change only with:

- New ADR or explicit lockfile update commit.
- Regression tests or eval cases for changed behavior.
- Migration/backward compatibility notes when public or stored contracts change.
- Secret-scan clean result.
