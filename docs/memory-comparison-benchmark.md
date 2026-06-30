# Memory Comparison Benchmark

This runner compares memo-stack / Infinity Context with mem0 using the same
high-level pipeline used by public memory benchmark runners:

```text
ingest -> search -> answer -> judge
```

It is separate from the existing `public-benchmark` command. The existing
runner checks retrieval and evidence coverage. This runner preserves each
pipeline stage for side-by-side accuracy, retrieval, latency, token/context and
failure analysis.

## Command

```sh
MEMORY_SERVICE_TOKEN=... \
MEM0_API_KEY=... \
MEMORY_OPENAI_API_KEY=... \
MEMORY_COMPARISON_ANSWERER_MODEL=... \
MEMORY_COMPARISON_JUDGE_MODEL=... \
MEMORY_COMPARISON_ANSWERER_INPUT_USD_PER_1M=... \
MEMORY_COMPARISON_ANSWERER_OUTPUT_USD_PER_1M=... \
MEMORY_COMPARISON_JUDGE_INPUT_USD_PER_1M=... \
MEMORY_COMPARISON_JUDGE_OUTPUT_USD_PER_1M=... \
python -m infinity_context_server.eval memory-comparison-benchmark \
  --dataset ./datasets/locomo10.json \
  --memo-api-url http://127.0.0.1:8000 \
  --mem0-url http://127.0.0.1:8888 \
  --mem0-api-key-env MEM0_API_KEY \
  --benchmark locomo \
  --max-cases 20 \
  --capability single-hop \
  --top-k 200 \
  --top-k-cutoff 10 \
  --top-k-cutoff 20 \
  --top-k-cutoff 50 \
  --top-k-cutoff 200 \
  --answerer-provider openai \
  --judge-provider openai \
  --answerer-input-usd-per-1m 2.50 \
  --answerer-output-usd-per-1m 10.00 \
  --judge-input-usd-per-1m 2.50 \
  --judge-output-usd-per-1m 10.00 \
  --allow-live \
  --allow-paid-llm \
  --run-id locomo-side-by-side-sandbox-001 \
  --report-out .e2e-artifacts/memory-comparison-locomo.json
```

`--mem0-url` is the self-hosted mem0 OSS REST server base URL. The adapter uses
the OSS endpoints `POST /memories`, `POST /search` and `DELETE /memories`; it
does not target the hosted mem0 Platform `/v3` API.
For OSS search requests, the adapter sends scoped entity ids through `filters`
and uses `top_k` for the requested retrieval count.

Use deterministic answer/judge for a no-paid dry run by omitting
`--answerer-provider openai`, `--judge-provider openai` and `--allow-paid-llm`.

### Codex CLI Answer/Judge

For local manual runs without an OpenAI API key, use Codex CLI as the answerer
and judge:

```sh
MEMORY_SERVICE_TOKEN=local-dev-token \
python -m infinity_context_server.eval memory-comparison-benchmark \
  --dataset ./datasets/locomo10.json \
  --memo-api-url http://127.0.0.1:8000 \
  --mem0-url http://127.0.0.1:8888 \
  --benchmark locomo \
  --max-cases 20 \
  --top-k 200 \
  --top-k-cutoff 10 \
  --top-k-cutoff 20 \
  --top-k-cutoff 50 \
  --top-k-cutoff 200 \
  --answerer-provider codex \
  --judge-provider codex \
  --answerer-model gpt-5.5 \
  --judge-model gpt-5.5 \
  --codex-timeout-seconds 180 \
  --allow-live \
  --run-id locomo-side-by-side-codex-sandbox-001 \
  --report-out .e2e-artifacts/memory-comparison-locomo-codex.json
```

The Codex provider shells out to `codex exec` with `--ephemeral`,
`--ignore-user-config`, `--ignore-rules`, `--sandbox read-only` and
`approval_policy="never"`. It uses only prompt evidence and estimates token
usage locally because Codex CLI does not expose benchmark token usage through
this adapter.

Model defaults:

- `--answerer-provider codex` and `--judge-provider codex` default to
  `gpt-5.5`, or `MEMORY_COMPARISON_CODEX_MODEL` when set.
- mem0's benchmark README lists common benchmark defaults as `gpt-4o` for
  answerer/judge, while its published OSS extraction-model LongMemEval table
  says those runs used GPT-5 as answerer and judge.
- Local Codex accounts may not expose literal `gpt-5`; if so, `gpt-5.5` is the
  closest currently usable Codex-side approximation, not an exact reproduction.

## Safety Gates

- `--allow-live` is required before the command calls memo-stack or mem0 HTTP
  endpoints.
- `--allow-paid-llm` is required before OpenAI answerer or judge calls.
- `--answerer-provider codex` / `--judge-provider codex` do not require
  `--allow-paid-llm` or an OpenAI API key, but they do consume the local Codex
  account/session quota.
- OpenAI models are explicit: pass `--answerer-model` / `--judge-model` or set
  `MEMORY_COMPARISON_ANSWERER_MODEL` / `MEMORY_COMPARISON_JUDGE_MODEL`.
- OpenAI key is read from `MEMORY_OPENAI_API_KEY` by default, with
  `OPENAI_API_KEY` as fallback. Do not commit keys or generated raw provider
  payloads.
- Codex mode only replaces the benchmark answerer/judge. A self-hosted mem0 OSS
  backend still needs its own extraction and embedding providers. The mem0
  default uses OpenAI; for a fully no-OpenAI run, configure mem0 with a local
  provider such as Ollama and make sure the required local models are running.
- Optional mem0 OSS API key is read from `MEM0_API_KEY` by default and sent as
  `X-API-Key` when present. Leave it unset only for explicitly auth-disabled
  local mem0 servers.
- By default the runner deletes the isolated mem0 `user_id` / `run_id` before
  ingest. That mem0 endpoint requires an admin-capable key or `AUTH_DISABLED=true`.
  If you only have a non-admin API key, pass `--mem0-skip-reset` and use a fresh
  `--run-id` so the run still uses isolated state.
- Token cost reporting uses explicit USD-per-1M-token rates from CLI flags or
  `MEMORY_COMPARISON_*_USD_PER_1M` env vars. The runner does not hardcode
  provider prices.
- Token cost scope is answerer/judge only. Backend-internal ingest/search
  provider costs are reported as unmeasured because they are not observable
  through the generic HTTP comparison ports.
- The memo-stack backend isolates state with a run-specific benchmark space.
- The mem0 backend uses a run-specific `user_id` / `run_id` and deletes that
  isolated user/run at startup by default.
- Corpus reuse is keyed by memory scope, thread and source content fingerprint;
  failed ingests are not cached for later questions in the same conversation.
- Any nonzero backend `items_failed` ingest result is scored as an `ingest_failed`
  stage failure and does not proceed to search for that case.

## Report Shape

The JSON report includes:

- per-backend accuracy and category/group breakdown;
- LoCoMo category 5 reported in `by_category` with unscored counts but excluded
  from scored accuracy;
- retrieved memory count, retrieval recall and missing expected terms;
- ingest/search/generation/judge latency averages;
- context token estimates, answerer/judge token usage and configured token cost;
- memo-stack vs mem0 deltas for accuracy, retrieval recall, retrieved count,
  latency, context tokens and token cost;
- configured top-k cutoff metrics, with pre-cutoff stage failures counted as
  failed scored cases;
- per-case failure analysis with backend, group, score, retrieval recall and
  missing terms;
- backend reset/ingest/search/answer/judge exceptions as scored stage failures with
  redacted error metadata.
- failed HTTP ingest operations include status code, reason phrase and a short
  redacted response preview when the backend returns one.
