from __future__ import annotations

from pathlib import Path

from memo_stack_cli.config import init_local_config, load_config
from memo_stack_cli.mcp_config import render_mcp_config, write_mcp_config


def test_cli_init_config_is_idempotent_and_keeps_token(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("MEMO_STACK_HOME", str(home))

    first = init_local_config(home=home, repo_dir=repo)
    first_token = first.service_token
    second = init_local_config(home=home, repo_dir=repo)

    assert first_token.startswith("mst_")
    assert second.service_token == first_token
    assert second.config_path.exists()
    assert second.env_path.exists()
    assert "MEMORY_SERVICE_TOKEN=" in second.env_path.read_text(encoding="utf-8")


def test_cli_load_config_supports_env_overrides(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    init_local_config(home=home, repo_dir=repo)
    monkeypatch.setenv("MEMO_STACK_HOME", str(home))
    monkeypatch.setenv("MEMORY_MCP_API_URL", "http://127.0.0.1:9999")
    monkeypatch.setenv("MEMORY_MCP_AUTH_TOKEN", "override-token")

    config = load_config()

    assert config.api_url == "http://127.0.0.1:9999"
    assert config.service_token == "override-token"


def test_mcp_config_redacts_token_by_default(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    (repo / "plugins" / "memo-stack-agent-plugin" / "bin").mkdir(parents=True)
    (repo / "plugins" / "memo-stack-agent-plugin" / "bin" / "memo-stack-mcp").write_text(
        "#!/usr/bin/env bash\n",
        encoding="utf-8",
    )
    config = init_local_config(home=home, repo_dir=repo)

    rendered = render_mcp_config(agent="codex", config=config)
    written = write_mcp_config(agent="codex", config=config)

    assert config.service_token not in rendered
    assert "${MEMORY_MCP_AUTH_TOKEN}" in rendered
    assert written.read_text(encoding="utf-8") == rendered + "\n"
