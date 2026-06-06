PYTHON ?= .venv/bin/python
RUFF ?= .venv/bin/ruff
COMPOSE ?= docker compose
MEMORY_SERVER_ENV ?= MEMORY_AUTO_CREATE_SCHEMA=true MEMORY_SERVICE_TOKEN=local-dev-token
PLUGIN_KIT_AI ?= scripts/plugin-kit-ai-local
MEMORY_AGENT_PLUGIN_ROOT ?= plugins/memory-agent-plugin
MEMORY_AGENT_CURSOR_WORKSPACE_PLUGIN_ROOT ?= plugins/memory-agent-plugin-cursor-workspace
MEMORY_AGENT_PLUGIN_ROOTS ?= $(MEMORY_AGENT_PLUGIN_ROOT) $(MEMORY_AGENT_CURSOR_WORKSPACE_PLUGIN_ROOT)
MEMORY_AGENT_PLUGIN_VALIDATE_TARGETS ?= codex-package claude gemini opencode cursor
MEMORY_AGENT_CURSOR_WORKSPACE_PLUGIN_VALIDATE_TARGETS ?= cursor-workspace
MEMORY_AGENT_INSTALL_TARGETS ?= codex claude gemini opencode cursor
MEMORY_AGENT_SMOKE_POSTGRES_PORT ?= 55429
MEMORY_AGENT_SMOKE_SERVER_PORT ?= 17788
MEMORY_PROD_CONFIDENCE_POSTGRES_PORT ?= 55431
MEMORY_PROD_CONFIDENCE_SERVER_PORT ?= 17791

.PHONY: memory-format
memory-format:
	$(RUFF) format .

.PHONY: memory-lint
memory-lint:
	$(RUFF) check .

.PHONY: memory-test-unit
memory-test-unit:
	$(PYTHON) -m pytest tests/unit

.PHONY: memory-test-all
memory-test-all:
	$(PYTHON) -m pytest

.PHONY: memory-test-application
memory-test-application:
	$(PYTHON) -m pytest tests/unit/test_domain_fact.py tests/unit/test_facts_api.py tests/unit/test_legacy_and_context_api.py tests/unit/test_suggestions_api.py

.PHONY: memory-test-integration
memory-test-integration:
	$(PYTHON) -m pytest tests/unit/test_provider_adapters.py tests/unit/test_worker_eval.py

.PHONY: memory-test-e2e
memory-test-e2e:
	$(PYTHON) -m pytest tests/e2e

.PHONY: memory-scale-chaos-load-e2e
memory-scale-chaos-load-e2e:
	$(PYTHON) -m pytest tests/e2e/test_memory_scale_chaos_load_e2e.py -q

.PHONY: memory-eval
memory-eval:
	$(PYTHON) -m memory_server eval run --suite small-golden
	$(PYTHON) -m memory_server eval run --suite quality-golden
	$(PYTHON) -m memory_server eval snapshots --suite prompt-contract

.PHONY: memory-test-quality
memory-test-quality: memory-lint memory-test-all memory-eval

.PHONY: memory-secret-scan
memory-secret-scan:
	@! rg -n '\bsk-(proj-)?[A-Za-z0-9_-]{40,}\b' . \
		-g '!**/__pycache__/**' \
		-g '!tests/**' \
		-g '!*.lock' \
		-g '!uv.lock' \
		-g '!poetry.lock'

.PHONY: memory-prod-confidence
memory-prod-confidence:
	@set -e; \
	cleanup() { $(MAKE) memory-down >/dev/null || true; }; \
	trap cleanup EXIT INT TERM; \
	$(MAKE) memory-plugin-test; \
	$(MAKE) memory-test-quality; \
	$(MAKE) memory-agent-install-doctor; \
	MEMORY_POSTGRES_PORT=$${MEMORY_POSTGRES_PORT:-$(MEMORY_PROD_CONFIDENCE_POSTGRES_PORT)} MEMORY_SERVER_PORT=$${MEMORY_SERVER_PORT:-$(MEMORY_PROD_CONFIDENCE_SERVER_PORT)} $(MAKE) memory-agent-live-smoke; \
	MEMORY_POSTGRES_PORT=$${MEMORY_POSTGRES_PORT:-$(MEMORY_PROD_CONFIDENCE_POSTGRES_PORT)} MEMORY_SERVER_PORT=$${MEMORY_SERVER_PORT:-$(MEMORY_PROD_CONFIDENCE_SERVER_PORT)} $(MAKE) memory-agent-live-smoke-agents; \
	$(MAKE) memory-agent-auth-doctor; \
	git diff --check; \
	$(MAKE) memory-secret-scan

.PHONY: memory-prod-confidence-strict
memory-prod-confidence-strict:
	@set -e; \
	cleanup() { $(MAKE) memory-down >/dev/null || true; }; \
	trap cleanup EXIT INT TERM; \
	$(MAKE) memory-prod-confidence-strict-preflight; \
	$(MAKE) memory-plugin-test; \
	$(MAKE) memory-test-quality; \
	$(MAKE) memory-agent-install-doctor; \
	$(MAKE) memory-full-provider-canary; \
	MEMORY_POSTGRES_PORT=$${MEMORY_POSTGRES_PORT:-$(MEMORY_PROD_CONFIDENCE_POSTGRES_PORT)} MEMORY_SERVER_PORT=$${MEMORY_SERVER_PORT:-$(MEMORY_PROD_CONFIDENCE_SERVER_PORT)} $(MAKE) memory-agent-live-smoke; \
	MEMORY_POSTGRES_PORT=$${MEMORY_POSTGRES_PORT:-$(MEMORY_PROD_CONFIDENCE_POSTGRES_PORT)} MEMORY_SERVER_PORT=$${MEMORY_SERVER_PORT:-$(MEMORY_PROD_CONFIDENCE_SERVER_PORT)} $(MAKE) memory-agent-live-smoke-agents-strict; \
	git diff --check; \
	$(MAKE) memory-secret-scan

.PHONY: memory-prod-confidence-full
memory-prod-confidence-full: memory-prod-confidence-strict

.PHONY: memory-prod-confidence-strict-preflight
memory-prod-confidence-strict-preflight:
	@test -n "$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY:-}}" || (echo "Set MEMORY_OPENAI_API_KEY or OPENAI_API_KEY before running strict prod confidence."; exit 1)
	$(MAKE) memory-agent-auth-doctor-strict

.PHONY: memory-smoke
memory-smoke:
	MEMORY_SMOKE_API_URL=$${MEMORY_SMOKE_API_URL:-http://127.0.0.1:7788} MEMORY_SMOKE_AUTH_TOKEN=$${MEMORY_SMOKE_AUTH_TOKEN:-local-dev-token} $(PYTHON) examples/integration_memory_smoke.py

.PHONY: memory-mcp-smoke
memory-mcp-smoke:
	MEMORY_MCP_API_URL=$${MEMORY_MCP_API_URL:-http://127.0.0.1:7788} MEMORY_MCP_AUTH_TOKEN=$${MEMORY_MCP_AUTH_TOKEN:-local-dev-token} MEMORY_MCP_WRITE_MODE=direct MEMORY_MCP_DELETE_MODE=explicit MEMORY_MCP_INGEST_MODE=allowed $(PYTHON) examples/mcp_agent_smoke.py

.PHONY: memory-plugin-generate
memory-plugin-generate:
	@set -e; \
	for plugin_root in $(MEMORY_AGENT_PLUGIN_ROOTS); do \
		$(PLUGIN_KIT_AI) generate $$plugin_root; \
	done

.PHONY: memory-plugin-check
memory-plugin-check:
	@set -e; \
	for plugin_root in $(MEMORY_AGENT_PLUGIN_ROOTS); do \
		$(PLUGIN_KIT_AI) generate $$plugin_root --check; \
	done

.PHONY: memory-plugin-validate
memory-plugin-validate:
	@set -e; \
	for target in $(MEMORY_AGENT_PLUGIN_VALIDATE_TARGETS); do \
		echo "Validating memory agent plugin for $$target"; \
		$(PLUGIN_KIT_AI) validate $(MEMORY_AGENT_PLUGIN_ROOT) --platform $$target --strict; \
	done; \
	for target in $(MEMORY_AGENT_CURSOR_WORKSPACE_PLUGIN_VALIDATE_TARGETS); do \
		echo "Validating memory agent cursor workspace plugin for $$target"; \
		$(PLUGIN_KIT_AI) validate $(MEMORY_AGENT_CURSOR_WORKSPACE_PLUGIN_ROOT) --platform $$target --strict; \
	done

.PHONY: memory-plugin-doctor
memory-plugin-doctor:
	MEMORY_MCP_API_URL=$${MEMORY_MCP_API_URL:-http://127.0.0.1:7788} MEMORY_MCP_AUTH_TOKEN=$${MEMORY_MCP_AUTH_TOKEN:-local-dev-token} $(MEMORY_AGENT_PLUGIN_ROOT)/bin/memory-mcp-doctor
	MEMORY_MCP_API_URL=$${MEMORY_MCP_API_URL:-http://127.0.0.1:7788} MEMORY_MCP_AUTH_TOKEN=$${MEMORY_MCP_AUTH_TOKEN:-local-dev-token} $(MEMORY_AGENT_CURSOR_WORKSPACE_PLUGIN_ROOT)/bin/memory-mcp-doctor

.PHONY: memory-plugin-e2e
memory-plugin-e2e: memory-plugin-check
	$(PYTHON) -m pytest tests/e2e/test_memory_agent_plugin_e2e.py -q

.PHONY: memory-plugin-test
memory-plugin-test: memory-plugin-check memory-plugin-validate memory-plugin-e2e

.PHONY: memory-capture-test
memory-capture-test:
	$(PYTHON) -m pytest tests/unit/test_capture_api.py tests/unit/test_capture_worker.py tests/unit/test_memory_taxonomy_mapping.py tests/unit/test_schema_migrations.py -q

.PHONY: memory-capture-e2e
memory-capture-e2e:
	$(PYTHON) -m pytest tests/unit/test_capture_api.py tests/unit/test_capture_worker.py -q

.PHONY: memory-hook-capture-smoke
memory-hook-capture-smoke:
	$(PYTHON) -m pytest tests/unit/test_plugin_hook_capture.py tests/unit/test_capture_host_fixtures.py -q

.PHONY: memory-auto-memory-eval
memory-auto-memory-eval:
	$(PYTHON) -m memory_server eval run --suite auto-memory-golden

.PHONY: memory-auto-memory-quality
memory-auto-memory-quality: memory-capture-test memory-hook-capture-smoke memory-auto-memory-eval
	$(PYTHON) -m pytest tests/unit/test_mcp_adapter.py -q

.PHONY: memory-agent-install-dry-run
memory-agent-install-dry-run:
	$(PYTHON) scripts/install_memory_agent_plugin.py --dry-run

.PHONY: memory-agent-install
memory-agent-install:
	$(PYTHON) scripts/install_memory_agent_plugin.py

.PHONY: memory-agent-install-doctor
memory-agent-install-doctor:
	$(PLUGIN_KIT_AI) integrations list
	$(PLUGIN_KIT_AI) integrations doctor
	$(PYTHON) scripts/agent_install_verification.py install-doctor

.PHONY: memory-agent-live-smoke
memory-agent-live-smoke:
	MEMORY_POSTGRES_PORT=$${MEMORY_POSTGRES_PORT:-$(MEMORY_AGENT_SMOKE_POSTGRES_PORT)} MEMORY_SERVER_PORT=$${MEMORY_SERVER_PORT:-$(MEMORY_AGENT_SMOKE_SERVER_PORT)} $(MAKE) memory-stack-up-lite
	MEMORY_MCP_API_URL=$${MEMORY_MCP_API_URL:-http://127.0.0.1:$${MEMORY_SERVER_PORT:-$(MEMORY_AGENT_SMOKE_SERVER_PORT)}} MEMORY_MCP_AUTH_TOKEN=$${MEMORY_MCP_AUTH_TOKEN:-local-dev-token} $(PYTHON) scripts/agent_install_verification.py live-smoke

.PHONY: memory-agent-live-smoke-agents
memory-agent-live-smoke-agents:
	MEMORY_POSTGRES_PORT=$${MEMORY_POSTGRES_PORT:-$(MEMORY_AGENT_SMOKE_POSTGRES_PORT)} MEMORY_SERVER_PORT=$${MEMORY_SERVER_PORT:-$(MEMORY_AGENT_SMOKE_SERVER_PORT)} $(MAKE) memory-stack-up-lite
	MEMORY_MCP_API_URL=$${MEMORY_MCP_API_URL:-http://127.0.0.1:$${MEMORY_SERVER_PORT:-$(MEMORY_AGENT_SMOKE_SERVER_PORT)}} MEMORY_MCP_AUTH_TOKEN=$${MEMORY_MCP_AUTH_TOKEN:-local-dev-token} $(PYTHON) scripts/agent_install_verification.py live-smoke --run-agent-cli

.PHONY: memory-agent-live-smoke-agents-strict
memory-agent-live-smoke-agents-strict:
	MEMORY_POSTGRES_PORT=$${MEMORY_POSTGRES_PORT:-$(MEMORY_AGENT_SMOKE_POSTGRES_PORT)} MEMORY_SERVER_PORT=$${MEMORY_SERVER_PORT:-$(MEMORY_AGENT_SMOKE_SERVER_PORT)} $(MAKE) memory-stack-up-lite
	MEMORY_MCP_API_URL=$${MEMORY_MCP_API_URL:-http://127.0.0.1:$${MEMORY_SERVER_PORT:-$(MEMORY_AGENT_SMOKE_SERVER_PORT)}} MEMORY_MCP_AUTH_TOKEN=$${MEMORY_MCP_AUTH_TOKEN:-local-dev-token} $(PYTHON) scripts/agent_install_verification.py live-smoke --run-agent-cli --strict-agent-cli

.PHONY: memory-agent-auth-doctor
memory-agent-auth-doctor:
	$(PYTHON) scripts/agent_install_verification.py agent-auth-doctor

.PHONY: memory-agent-auth-doctor-strict
memory-agent-auth-doctor-strict:
	$(PYTHON) scripts/agent_install_verification.py agent-auth-doctor --strict

.PHONY: memory-agent-auth-repair
memory-agent-auth-repair:
	@if [ ! -t 0 ]; then \
		echo "Run this target from an interactive terminal: make memory-agent-auth-repair"; \
		exit 1; \
	fi
	@echo "Repairing Claude auth through the official Claude CLI login flow..."
	claude auth login --claudeai
	@echo "Repairing OpenCode OpenAI auth through the official OpenCode provider login flow..."
	opencode providers login --provider openai
	$(MAKE) memory-agent-auth-doctor-strict

.PHONY: memory-doctor
memory-doctor:
	$(PYTHON) -m memory_server.doctor

.PHONY: memory-db-upgrade
memory-db-upgrade:
	$(PYTHON) -m memory_server.db upgrade

.PHONY: memory-seed-defaults
memory-seed-defaults:
	$(PYTHON) -m memory_server.admin seed-defaults

.PHONY: memory-worker-once
memory-worker-once:
	$(PYTHON) -m memory_server.worker --once

.PHONY: memory-up
memory-up:
	$(COMPOSE) up -d memory_postgres

.PHONY: memory-up-full-deps
memory-up-full-deps:
	$(COMPOSE) --profile full up -d memory_postgres memory_qdrant memory_neo4j

.PHONY: memory-stack-up
memory-stack-up:
	$(MAKE) memory-stack-up-lite

.PHONY: memory-stack-up-lite
memory-stack-up-lite:
	$(COMPOSE) --profile lite up -d memory_server memory_worker

.PHONY: memory-stack-up-full
memory-stack-up-full:
	@test -n "$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY:-}}" || (echo "Set MEMORY_OPENAI_API_KEY or OPENAI_API_KEY before starting the full profile."; exit 1)
	MEMORY_OPENAI_API_KEY="$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY}}" OPENAI_API_KEY="$${OPENAI_API_KEY:-$${MEMORY_OPENAI_API_KEY}}" $(COMPOSE) --profile full up -d memory_server_full memory_worker_full

.PHONY: memory-stack-smoke
memory-stack-smoke:
	$(MAKE) memory-stack-up-lite
	for i in $$(seq 1 90); do curl -fsS http://127.0.0.1:7788/v1/health >/dev/null && break; if [ $$i -eq 90 ]; then $(COMPOSE) logs --tail=120 memory_server; exit 1; fi; sleep 1; done
	$(MAKE) memory-smoke

.PHONY: memory-stack-smoke-full
memory-stack-smoke-full:
	$(MAKE) memory-stack-up-full
	for i in $$(seq 1 120); do curl -fsS http://127.0.0.1:7788/v1/health >/dev/null && break; if [ $$i -eq 120 ]; then $(COMPOSE) logs --tail=120 memory_server_full; exit 1; fi; sleep 1; done
	$(MAKE) memory-smoke
	$(MAKE) memory-mcp-smoke

.PHONY: memory-clean-full-smoke
memory-clean-full-smoke:
	@test -n "$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY:-}}" || (echo "Set MEMORY_OPENAI_API_KEY or OPENAI_API_KEY before running clean full smoke."; exit 1)
	export MEMORY_OPENAI_API_KEY="$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY}}"; \
	export OPENAI_API_KEY="$${OPENAI_API_KEY:-$${MEMORY_OPENAI_API_KEY}}"; \
	$(PYTHON) scripts/clean_full_smoke.py

.PHONY: memory-clean-full-mcp-smoke
memory-clean-full-mcp-smoke:
	@test -n "$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY:-}}" || (echo "Set MEMORY_OPENAI_API_KEY or OPENAI_API_KEY before running clean full MCP smoke."; exit 1)
	export MEMORY_CLEAN_SMOKE_SKIP_MCP=false; \
	export MEMORY_OPENAI_API_KEY="$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY}}"; \
	export OPENAI_API_KEY="$${OPENAI_API_KEY:-$${MEMORY_OPENAI_API_KEY}}"; \
	$(PYTHON) scripts/clean_full_smoke.py

.PHONY: memory-agent-behavior-bench
memory-agent-behavior-bench:
	@test -n "$${MEMORY_AGENT_BENCH_MODEL:-}" || (echo "Set MEMORY_AGENT_BENCH_MODEL before running agent behavior benchmark."; exit 1)
	@test -n "$${MEMORY_AGENT_BENCH_OPENAI_API_KEY:-$${OPENAI_API_KEY:-$${MEMORY_OPENAI_API_KEY:-}}}" || (echo "Set MEMORY_AGENT_BENCH_OPENAI_API_KEY, OPENAI_API_KEY or MEMORY_OPENAI_API_KEY before running agent behavior benchmark."; exit 1)
	export MEMORY_CLEAN_SMOKE_AGENT_BENCH=true; \
	export MEMORY_CLEAN_SMOKE_SKIP_MCP=false; \
	export MEMORY_CLEAN_SMOKE_WORKER_TIMEOUT_SECONDS="$${MEMORY_CLEAN_SMOKE_WORKER_TIMEOUT_SECONDS:-420}"; \
	export MEMORY_AGENT_BENCH_LLM_TIMEOUT_SECONDS="$${MEMORY_AGENT_BENCH_LLM_TIMEOUT_SECONDS:-360}"; \
	export MEMORY_AGENT_BENCH_FAIL_ON_WORKER_ERROR="$${MEMORY_AGENT_BENCH_FAIL_ON_WORKER_ERROR:-true}"; \
	export MEMORY_AGENT_BENCH_OPENAI_API_KEY="$${MEMORY_AGENT_BENCH_OPENAI_API_KEY:-$${OPENAI_API_KEY:-$${MEMORY_OPENAI_API_KEY}}}"; \
	export MEMORY_OPENAI_API_KEY="$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY:-$${MEMORY_AGENT_BENCH_OPENAI_API_KEY}}}"; \
	export OPENAI_API_KEY="$${OPENAI_API_KEY:-$${MEMORY_OPENAI_API_KEY:-$${MEMORY_AGENT_BENCH_OPENAI_API_KEY}}}"; \
	$(PYTHON) scripts/clean_full_smoke.py

.PHONY: memory-agent-realistic-bench
memory-agent-realistic-bench:
	@test -n "$${MEMORY_AGENT_BENCH_MODEL:-}" || (echo "Set MEMORY_AGENT_BENCH_MODEL before running realistic agent behavior benchmark."; exit 1)
	@test -n "$${MEMORY_AGENT_BENCH_OPENAI_API_KEY:-$${OPENAI_API_KEY:-$${MEMORY_OPENAI_API_KEY:-}}}" || (echo "Set MEMORY_AGENT_BENCH_OPENAI_API_KEY, OPENAI_API_KEY or MEMORY_OPENAI_API_KEY before running realistic agent behavior benchmark."; exit 1)
	export MEMORY_CLEAN_SMOKE_AGENT_BENCH=true; \
	export MEMORY_CLEAN_SMOKE_SKIP_MCP=false; \
	export MEMORY_AGENT_BENCH_SCENARIO_SET=realistic; \
	export MEMORY_CLEAN_SMOKE_WORKER_TIMEOUT_SECONDS="$${MEMORY_CLEAN_SMOKE_WORKER_TIMEOUT_SECONDS:-420}"; \
	export MEMORY_AGENT_BENCH_LLM_TIMEOUT_SECONDS="$${MEMORY_AGENT_BENCH_LLM_TIMEOUT_SECONDS:-360}"; \
	export MEMORY_AGENT_BENCH_FAIL_ON_WORKER_ERROR="$${MEMORY_AGENT_BENCH_FAIL_ON_WORKER_ERROR:-true}"; \
	export MEMORY_AGENT_BENCH_OPENAI_API_KEY="$${MEMORY_AGENT_BENCH_OPENAI_API_KEY:-$${OPENAI_API_KEY:-$${MEMORY_OPENAI_API_KEY}}}"; \
	export MEMORY_OPENAI_API_KEY="$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY:-$${MEMORY_AGENT_BENCH_OPENAI_API_KEY}}}"; \
	export OPENAI_API_KEY="$${OPENAI_API_KEY:-$${MEMORY_OPENAI_API_KEY:-$${MEMORY_AGENT_BENCH_OPENAI_API_KEY}}}"; \
	$(PYTHON) scripts/clean_full_smoke.py

.PHONY: memory-full-provider-canary
memory-full-provider-canary: memory-clean-full-mcp-smoke

.PHONY: memory-full-provider-canary-interactive
memory-full-provider-canary-interactive:
	@if [ -n "$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY:-}}" ]; then \
		$(MAKE) memory-full-provider-canary; \
	else \
		if [ ! -t 0 ]; then \
			echo "Set MEMORY_OPENAI_API_KEY or OPENAI_API_KEY, or run this target from an interactive terminal."; \
			exit 1; \
		fi; \
		printf "OpenAI key (input hidden): " >&2; \
		old_stty=$$(stty -g); \
		trap 'stty "$$old_stty" 2>/dev/null || true' EXIT INT TERM; \
		stty -echo; \
		IFS= read -r OPENAI_KEY; \
		stty "$$old_stty"; \
		trap - EXIT INT TERM; \
		printf "\n" >&2; \
		test -n "$$OPENAI_KEY" || (echo "OpenAI key is required."; exit 1); \
		MEMORY_OPENAI_API_KEY="$$OPENAI_KEY" OPENAI_API_KEY="$$OPENAI_KEY" $(MAKE) memory-full-provider-canary; \
		unset OPENAI_KEY; \
	fi

.PHONY: memory-prod-load-canary
memory-prod-load-canary:
	@test -n "$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY:-}}" || (echo "Set MEMORY_OPENAI_API_KEY or OPENAI_API_KEY before running prod load canary."; exit 1)
	export MEMORY_CLEAN_SMOKE_PROD_LOAD=true; \
	export MEMORY_CLEAN_SMOKE_SKIP_MCP=false; \
	export MEMORY_CLEAN_SMOKE_WORKER_TIMEOUT_SECONDS="$${MEMORY_CLEAN_SMOKE_WORKER_TIMEOUT_SECONDS:-420}"; \
	export MEMORY_OPENAI_API_KEY="$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY}}"; \
	export OPENAI_API_KEY="$${OPENAI_API_KEY:-$${MEMORY_OPENAI_API_KEY}}"; \
	$(PYTHON) scripts/clean_full_smoke.py

.PHONY: memory-down
memory-down:
	$(COMPOSE) --profile lite --profile full down

.PHONY: memory-server
memory-server:
	$(MEMORY_SERVER_ENV) $(PYTHON) -m memory_server.main
