PYTHON ?= .venv/bin/python
RUFF ?= .venv/bin/ruff
COMPOSE ?= docker compose
MEMORY_SERVER_ENV ?= MEMORY_AUTO_CREATE_SCHEMA=true MEMORY_SERVICE_TOKEN=local-dev-token
PLUGIN_KIT_AI ?= plugin-kit-ai
MEMORY_AGENT_PLUGIN_ROOT ?= plugins/memory-agent-plugin
MEMORY_AGENT_CURSOR_WORKSPACE_PLUGIN_ROOT ?= plugins/memory-agent-plugin-cursor-workspace
MEMORY_AGENT_PLUGIN_ROOTS ?= $(MEMORY_AGENT_PLUGIN_ROOT) $(MEMORY_AGENT_CURSOR_WORKSPACE_PLUGIN_ROOT)
MEMORY_AGENT_PLUGIN_VALIDATE_TARGETS ?= codex-package claude gemini opencode cursor
MEMORY_AGENT_CURSOR_WORKSPACE_PLUGIN_VALIDATE_TARGETS ?= cursor-workspace

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

.PHONY: memory-eval
memory-eval:
	$(PYTHON) -m memory_server eval run --suite small-golden
	$(PYTHON) -m memory_server eval run --suite quality-golden
	$(PYTHON) -m memory_server eval snapshots --suite prompt-contract

.PHONY: memory-test-quality
memory-test-quality: memory-lint memory-test-all memory-eval

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
	MEMORY_OPENAI_API_KEY="$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY}}" OPENAI_API_KEY="$${OPENAI_API_KEY:-$${MEMORY_OPENAI_API_KEY}}" $(PYTHON) scripts/clean_full_smoke.py

.PHONY: memory-clean-full-mcp-smoke
memory-clean-full-mcp-smoke:
	@test -n "$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY:-}}" || (echo "Set MEMORY_OPENAI_API_KEY or OPENAI_API_KEY before running clean full MCP smoke."; exit 1)
	MEMORY_CLEAN_SMOKE_SKIP_MCP=false MEMORY_OPENAI_API_KEY="$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY}}" OPENAI_API_KEY="$${OPENAI_API_KEY:-$${MEMORY_OPENAI_API_KEY}}" $(PYTHON) scripts/clean_full_smoke.py

.PHONY: memory-down
memory-down:
	$(COMPOSE) --profile lite --profile full down

.PHONY: memory-server
memory-server:
	$(MEMORY_SERVER_ENV) $(PYTHON) -m memory_server.main
