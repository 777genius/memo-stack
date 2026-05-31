from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_docker_compose_bootstraps_local_server_before_http() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "pg_isready -U memory -d memory" in compose
    assert "condition: service_healthy" in compose
    assert "python -m memory_server.db upgrade" in compose
    assert "python -m memory_server.admin seed-defaults" in compose
    assert "http://127.0.0.1:7788/v1/health" in compose


def test_makefile_has_one_command_stack_smoke_target() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert ".PHONY: memory-stack-smoke" in makefile
    assert "docker compose up -d memory_server" in makefile
    assert "curl -fsS http://127.0.0.1:7788/v1/health" in makefile
    assert "$(MAKE) memory-smoke" in makefile
