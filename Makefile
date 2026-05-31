PYTHON ?= .venv/bin/python
RUFF ?= .venv/bin/ruff
COMPOSE ?= docker compose
MEMORY_SERVER_ENV ?= MEMORY_AUTO_CREATE_SCHEMA=true MEMORY_SERVICE_TOKEN=local-dev-token

.PHONY: memory-format
memory-format:
	$(RUFF) format .

.PHONY: memory-lint
memory-lint:
	$(RUFF) check .

.PHONY: memory-test-unit
memory-test-unit:
	$(PYTHON) -m pytest

.PHONY: memory-test-application
memory-test-application:
	$(PYTHON) -m pytest tests/unit/test_domain_fact.py tests/unit/test_facts_api.py tests/unit/test_legacy_and_context_api.py tests/unit/test_suggestions_api.py

.PHONY: memory-test-integration
memory-test-integration:
	$(PYTHON) -m pytest tests/unit/test_provider_adapters.py tests/unit/test_worker_eval.py

.PHONY: memory-test-e2e
memory-test-e2e:
	$(PYTHON) -m pytest tests/unit/test_legacy_and_context_api.py tests/unit/test_worker_eval.py

.PHONY: memory-eval
memory-eval:
	$(PYTHON) -m memory_server eval run --suite small-golden
	$(PYTHON) -m memory_server eval snapshots --suite prompt-contract

.PHONY: memory-test-quality
memory-test-quality: memory-lint memory-test-application memory-test-integration memory-test-e2e memory-eval

.PHONY: memory-smoke
memory-smoke:
	MEMORY_SMOKE_API_URL=$${MEMORY_SMOKE_API_URL:-http://127.0.0.1:7788} MEMORY_SMOKE_AUTH_TOKEN=$${MEMORY_SMOKE_AUTH_TOKEN:-local-dev-token} $(PYTHON) examples/integration_memory_smoke.py

.PHONY: memory-mcp-smoke
memory-mcp-smoke:
	MEMORY_MCP_API_URL=$${MEMORY_MCP_API_URL:-http://127.0.0.1:7788} MEMORY_MCP_AUTH_TOKEN=$${MEMORY_MCP_AUTH_TOKEN:-local-dev-token} $(PYTHON) examples/mcp_agent_smoke.py

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
	for i in $$(seq 1 90); do curl -fsS http://127.0.0.1:7788/v1/health >/dev/null && break; if [ $$i -eq 90 ]; then docker compose logs --tail=120 memory_server; exit 1; fi; sleep 1; done
	$(MAKE) memory-smoke

.PHONY: memory-stack-smoke-full
memory-stack-smoke-full:
	$(MAKE) memory-stack-up-full
	for i in $$(seq 1 120); do curl -fsS http://127.0.0.1:7788/v1/health >/dev/null && break; if [ $$i -eq 120 ]; then docker compose logs --tail=120 memory_server_full; exit 1; fi; sleep 1; done
	$(MAKE) memory-smoke
	$(MAKE) memory-mcp-smoke

.PHONY: memory-clean-full-smoke
memory-clean-full-smoke:
	@test -n "$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY:-}}" || (echo "Set MEMORY_OPENAI_API_KEY or OPENAI_API_KEY before running clean full smoke."; exit 1)
	MEMORY_OPENAI_API_KEY="$${MEMORY_OPENAI_API_KEY:-$${OPENAI_API_KEY}}" OPENAI_API_KEY="$${OPENAI_API_KEY:-$${MEMORY_OPENAI_API_KEY}}" $(PYTHON) scripts/clean_full_smoke.py

.PHONY: memory-down
memory-down:
	$(COMPOSE) --profile lite --profile full down

.PHONY: memory-server
memory-server:
	$(MEMORY_SERVER_ENV) $(PYTHON) -m memory_server.main
