PYTHON ?= .venv/bin/python
RUFF ?= .venv/bin/ruff
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
	$(PYTHON) -m memory_server.eval run --suite small-golden

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
	docker compose up -d memory_postgres memory_qdrant memory_neo4j

.PHONY: memory-stack-up
memory-stack-up:
	docker compose up -d memory_server

.PHONY: memory-down
memory-down:
	docker compose down

.PHONY: memory-server
memory-server:
	$(MEMORY_SERVER_ENV) $(PYTHON) -m memory_server.main
