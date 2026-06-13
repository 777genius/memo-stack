# Code Context Tools Benchmark

Date: 2026-06-13

Repository snapshot: `b942f92`

Benchmark worktree: `/private/tmp/memo-stack-context-bench-1781366224`

Repo size in the temporary worktree:

| Metric | Value |
| --- | ---: |
| `find . -type f` | 676 files |
| `rg --files` | 658 files |
| `du -sh .` | 14M |

## Tools

| Tool | Version used | Install/runtime path |
| --- | --- | --- |
| CodeGraph | `@colbymchenry/codegraph@1.0.0` | `npx` |
| codebase-memory-mcp | `0.8.1` | `npx` |
| Codanna | `0.9.22` | `cargo install` |
| Sverklo | `0.29.1` | `npm exec` |
| CodeGraphContext | `0.4.11` | local `cgc` |

Reference links checked:

- [CodeGraph GitHub](https://github.com/colbymchenry/codegraph)
- [codebase-memory-mcp GitHub](https://github.com/DeusData/codebase-memory-mcp)
- [Codanna GitHub](https://github.com/bartolli/codanna)
- [Serena docs](https://oraios.github.io/serena/01-about/000_intro.html)

## Cold Index

| Tool | Wall time | Indexed shape | Notes |
| --- | ---: | --- | --- |
| CodeGraph | 13.47s | 512 files, 11,083 nodes, 34,872 edges | Internal indexing time was 6.9s. The wall time includes `npx` startup. |
| codebase-memory-mcp | 7.09s | 617 files, 10,687 nodes, 46,638 edges | Internal elapsed time was 1.797s. Fastest cold index in this run. |
| Codanna | 17.46s | 19,168 symbols, 7,531 relationships | Install took 3m 09s. Semantic model was already available from cache. |
| Sverklo | 168.06s | 540 files, 7,895 chunks, 38,719 symbol references | First run downloaded about 90MB model data. Proof was noisy for this repo. |
| CodeGraphContext | 40.90s | graph created in CGC context | Indexing took 36.71s. It skipped 1,508 unresolved call relationships. |

## Query Scenarios

### Exact Symbol: `MemoryScope`

| Tool | Wall time | Output | Result quality |
| --- | ---: | ---: | --- |
| CodeGraph | 2.64s | 6.1KB | Correctly surfaced the frontend, SDK, core, and MCP `MemoryScope` definitions. Concise JSON. |
| codebase-memory-mcp | 1.16s | 3.9KB | Found 112 matches. Good graph search, but requires exact project name in multi-project cache. |
| Codanna | 0.55s | 25.3KB | Fastest exact search. Rich relationship output, but verbose. |
| CodeGraphContext | 1.68s | human table | Found 50 matches. Good table UX, but main table prints outside redirected stdout. |

### Discovery: `asset extraction`

| Tool | Wall time | Output | Result quality |
| --- | ---: | ---: | --- |
| CodeGraph | 2.65s | 25.3KB | Best one-shot agent answer. It returned related symbols, blast radius, callers, tests, and source code. |
| codebase-memory-mcp | 2.59s | 2.1KB | Useful exact-pattern results. CLI did not expose a working `semantic_query` command in this run. |
| Codanna | 0.78s | 7.0KB | Semantic results were relevant but narrower, mostly ports and extraction interfaces. |
| CodeGraphContext | 1.52s | human table | Useful content hit list with core use cases and repository methods. Less explanatory than CodeGraph. |

### Callers: `build_container`

| Tool | Wall time | Output | Result quality |
| --- | ---: | ---: | --- |
| CodeGraph | 1.66s | 3.4KB | Correct and compact caller list. Good agent ergonomics. |
| codebase-memory-mcp | 1.34s | 66B | `trace_path` returned no callers for the simple function name, although graph metadata showed inbound degree. Needs more API tuning. |
| Codanna | 0.06s | 11.1KB | Fastest and correct, with 17 callers. Output is detailed and verbose. |
| CodeGraphContext | 1.42s | human table | Returned 20 callers. Good for manual audit. |

## Ranking

1. CodeGraph - best daily agent UX. It gives the most useful one-shot answer for discovery and impact analysis, with compact enough output.
2. Codanna - best raw speed after install. It is strongest for exact symbols and caller/callee work, but setup is heavier and outputs are verbose.
3. codebase-memory-mcp - best cold indexing speed and promising team graph shape. Query ergonomics were weaker in this run, especially caller tracing.
4. CodeGraphContext - reliable manual audit tool already available locally, but indexing was slower and some call relationships were unresolved.
5. Sverklo - not recommended as the primary tool for this repo based on this cold run. It was too slow and the proof target was noisy.

## Top 3 Options

1. Use CodeGraph as the primary agent context tool, with Codanna as the fast exact graph helper. 🎯 9   🛡️ 8   🧠 5. Approximate change size: 10-20 lines of docs/config.
2. Pilot codebase-memory-mcp as a team-shared graph artifact before adopting it as primary. 🎯 8   🛡️ 7   🧠 6. Approximate change size: 10-30 lines of docs/config.
3. Keep CodeGraphContext as the default and add no new dependency yet. 🎯 6   🛡️ 8   🧠 2. Approximate change size: 0-5 lines.

## Recommendation

Use CodeGraph first if the goal is better agent navigation today. Add Codanna if exact symbol and caller queries need to be very fast. Re-test codebase-memory-mcp with qualified symbol names and team artifact sync before choosing it as the primary shared graph.

Do not use Sverklo as the main context engine for this repo until a faster, less noisy workflow is verified.

## Sync And Serena Notes

CodeGraph is local-first. Its public positioning says it auto-syncs on code changes, but this should be treated as local index refresh, not as team task assignment or shared human-agent memory. For team use, verify whether the `.codegraph` directory should be shared, ignored, or rebuilt per developer.

Serena is a different category. It is closer to an IDE/LSP toolkit for semantic retrieval, symbol-level editing, references, refactors, and diagnostics over MCP. CodeGraph and Codanna are better when the main need is a precomputed project graph for quick context retrieval. Serena is better when the agent needs IDE-like operations before editing.

CodeGraphContext in the local 777genius code-intelligence workflow is routed for graph questions through explicit CGC commands. The doctor skill is read-only and does not index projects. Do not assume CGC indexes every project in the background unless a separate local startup hook is configured.

## Repro Commands

```bash
npx -y @colbymchenry/codegraph@1.0.0 init .
npx -y codebase-memory-mcp@0.8.1 cli index_repository '{"repo_path":"/private/tmp/memo-stack-context-bench-1781366224"}'
codanna init
codanna index . --no-progress
npm exec --yes --package=sverklo@0.29.1 -- sverklo prove --no-write --guided --markdown .
cgc index . --context memo-stack-bench-1781366224
```

```bash
npx -y @colbymchenry/codegraph@1.0.0 query MemoryScope --json
npx -y codebase-memory-mcp@0.8.1 cli search_graph '{"project":"private-tmp-memo-stack-context-bench-1781366224","name_pattern":".*MemoryScope.*","limit":10}'
codanna retrieve search MemoryScope --limit 10 --json
cgc find pattern MemoryScope --context memo-stack-bench-1781366224
```

```bash
npx -y @colbymchenry/codegraph@1.0.0 explore asset extraction --max-files 5
npx -y codebase-memory-mcp@0.8.1 cli search_code '{"project":"private-tmp-memo-stack-context-bench-1781366224","pattern":"asset extraction","limit":5}'
codanna mcp semantic_search_with_context query:"asset extraction" limit:5 --json
cgc find content "asset extraction" --context memo-stack-bench-1781366224
```

```bash
npx -y @colbymchenry/codegraph@1.0.0 callers build_container --json
npx -y codebase-memory-mcp@0.8.1 cli trace_path '{"project":"private-tmp-memo-stack-context-bench-1781366224","function_name":"build_container","direction":"inbound","depth":2}'
codanna mcp find_callers build_container --json
cgc analyze callers build_container --context memo-stack-bench-1781366224
```
