# Memory Goal Coverage Matrix

Status: active proof matrix for the current memory production-hardening goal.

Date: 2026-06-18.

This file maps the product goal to proof surfaces in the repository. A row is
not considered complete because code exists. It is complete only when the
current code, tests and public contracts prove the behavior at the required
scope.

## Coverage Rules

- Canonical memory state must be proven through Postgres-backed domain and API
  flows.
- Derived indexes such as Qdrant, Graphiti and RAG are useful only after
  canonical rehydration proof exists.
- Provider-derived content is evidence, not authority.
- Review gates win over weak automation.
- Diagnostics must be bounded, redacted and stable for frontend and SDK clients.
- Obsidian and agent runtime flows are excluded from this goal's test surface.

## Goal Matrix

| Goal area | Required behavior | Current proof surface | Status | Next proof needed |
| --- | --- | --- | --- | --- |
| Stable baseline and commits | Work is split into conventional commits with status, diff, targeted gates and secret scan before each commit | Git history, command logs, `make memo-stack-secret-scan` | Partial | Keep using small commits for every new slice |
| Research lockfile | Product rules cover memory types, anchors vs tags, temporal validity, review gates, no hidden instruction memory, canonical and derived stores, scoring and provenance | `docs/memory-architecture-research-lockfile.md` | Strong | Keep changes additive or require ADR plus eval |
| Migration compatibility | Legacy anchors and relations map missing confidence, evidence refs and temporal fields to safe defaults | `tests/unit/test_memory_scope_transfer_legacy.py`, `tests/unit/test_memory_scope_transfer_redaction.py`, `tests/unit/test_postgres_mappers_legacy.py` | Strong | Add API payload compatibility checks when response DTOs change |
| Context Assembly v2 | Retrieval sources bounded, ranking reasons present, score signals redacted, provenance normalized, hybrid and temporal counters present | `tests/unit/test_context_diagnostics.py`, `tests/unit/test_context_packer.py`, `tests/unit/test_context_provider_consistency.py`, SDK diagnostics tests, context hydrator batch lookup tests | Strong | Add new call-count guards when introducing expensive rerankers or new derived collectors |
| Context quality eval pack | Superseded hidden, disputed hidden, similar project precision, same-name person/project separation, document evidence links, no-candidate precision, hybrid beats single source | `packages/memo_stack_server/memo_stack_server/eval_case_catalog.py`, `packages/memo_stack_server/memo_stack_server/eval_semantic_linking.py`, `tests/unit/test_worker_eval.py`, `tests/e2e/test_semantic_linking_quality_e2e.py` | Strong | Keep required case ids in scorecard when adding new quality cases |
| Semantic linking policy | Thresholds, relation-specific rules, deny rules, explainable reasons, pending vs auto-approve eligibility, caps and duplicate suppression | `packages/memo_stack_core/memo_stack_core/application/context_link_policy.py`, `tests/unit/test_context_link_policy.py` | Strong | Add user-facing docs for policy reason codes |
| Anchor lifecycle | People, events, projects and organizations support alias conflict checks, duplicate prevention, merge/split audit, evidence and temporal preservation | `tests/unit/test_anchor_lifecycle_api.py`, `tests/e2e/test_anchor_lifecycle_sdk_e2e.py` | Strong | Add scorecard gate for anchor lifecycle suite if it becomes release-critical |
| Temporal relation hardening | Relations expose observed and valid windows, supersedes and contradicts invalidate default context, stale is review/debug only | `tests/unit/test_fact_relations_api.py`, `tests/unit/test_context_provider_consistency.py`, SDK stale diagnostics tests | Strong | Add relative-time eval case for "was true last week, not now" |
| Review UX safety | Review modal and batch flows avoid optimistic unsafe updates and support filtered visible review | Browser UI JS tests and API review filter tests | Partial | Add frontend focus-trap and keyboard escape tests |
| API and SDK review flows | SDK can list, approve, reject, override target, batch review, list anchors/evidence and parse diagnostics | `tests/unit/test_sdk_contract.py`, `tests/e2e/test_context_link_batch_review_sdk_e2e.py`, `tests/e2e/test_manual_context_link_sdk_e2e.py` | Strong | Keep SDK typed diagnostics versioned with context contract |
| Observability and audit | Review actions, linking decisions, rejected candidates and context assembly counters are bounded and redacted | context diagnostics tests, context link review audit tests, redaction tests | Strong | Add migration/schema diagnostics if schema drift tooling changes |
| Performance guardrails | Candidate limits, evidence ref caps, diagnostics caps, batch caps and payload bounds are tested | `tests/unit/test_context_link_suggestion_guardrails.py`, `tests/unit/test_context_link_policy.py`, `tests/unit/test_context_packer.py`, review batch tests, context SQL call-count guards | Strong | Add source-ref batch loading for fact list/search if fact retrieval volume grows |
| Multimodal evidence | Documents, images, audio and video create evidence artifacts with page, bbox or time refs before semantic promotion | multimodal manifest tests, extraction adapter tests, capabilities SDK tests, provider-off/provider-on API extraction tests for image/audio/video | Strong | Add optional live-provider smoke under explicit env when paid provider keys are available |

## Release Gate Shortlist

Before calling this goal complete, run or justify:

```text
.venv/bin/python -m pytest tests/unit/test_context_link_policy.py
.venv/bin/python -m pytest tests/unit/test_context_diagnostics.py tests/unit/test_context_packer.py
.venv/bin/python -m pytest tests/unit/test_context_provider_consistency.py
.venv/bin/python -m pytest tests/unit/test_fact_relations_api.py
.venv/bin/python -m pytest tests/unit/test_anchor_lifecycle_api.py
.venv/bin/python -m pytest tests/unit/test_memory_scope_transfer_legacy.py tests/unit/test_memory_scope_transfer_redaction.py
.venv/bin/python -m pytest tests/unit/test_sdk_contract.py
.venv/bin/python -m pytest tests/unit/test_worker_eval.py -k semantic_linking
.venv/bin/python -m pytest tests/e2e/test_semantic_linking_quality_e2e.py
make memo-stack-secret-scan
```

Do not include Obsidian or real agent runtime tests in this gate.
