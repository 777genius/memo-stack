from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infinity_context_cli import cli
from infinity_context_cli.config import init_local_config, load_config
from infinity_context_cli.runtime import RuntimeResult


def test_cli_quickstart_initializes_and_writes_redacted_mcp_config(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("INFINITY_CONTEXT_HOME", str(home))

    exit_code = cli.main(
        [
            "quickstart",
            "--home",
            str(home),
            "--repo-dir",
            str(repo),
            "--no-start",
            "--agent",
            "codex",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    config = load_config(home)
    mcp_path = Path(payload["mcp_configs"][0]["path"])

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["runtime"] is None
    assert payload["mcp_configs"][0]["agent"] == "codex"
    assert payload["mcp_configs"][0]["token_included"] is False
    assert config.service_token not in captured.out
    assert config.service_token not in mcp_path.read_text(encoding="utf-8")
    assert "${MEMORY_MCP_AUTH_TOKEN}" in mcp_path.read_text(encoding="utf-8")
    assert str(home / ".env") in "\n".join(payload["next_steps"])


def test_cli_quickstart_starts_runtime_waits_for_status_and_redacts_output(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    raw_secret = "sk-proj-secretvalue1234567890"
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    init_local_config(home=home, repo_dir=repo)
    monkeypatch.setenv("INFINITY_CONTEXT_HOME", str(home))

    class FakeRuntime:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def up(self, compose_profile: str) -> RuntimeResult:
            return RuntimeResult(
                ok=True,
                command=("docker", "compose", "--profile", compose_profile, "up", "-d"),
                returncode=0,
                stdout=f"started with {raw_secret}",
                stderr="",
            )

    statuses = [
        {"ok": False, "api_url": "http://127.0.0.1:7788", "error": "ConnectError"},
        {"ok": True, "api_url": "http://127.0.0.1:7788"},
    ]

    def fake_status(_config) -> dict[str, Any]:
        return statuses.pop(0) if statuses else {"ok": True, "api_url": "http://127.0.0.1:7788"}

    monkeypatch.setattr(cli, "DockerComposeRuntime", FakeRuntime)
    monkeypatch.setattr(cli, "_status_payload", fake_status)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    exit_code = cli.main(
        [
            "quickstart",
            "--home",
            str(home),
            "--repo-dir",
            str(repo),
            "--wait-seconds",
            "1",
            "--agent",
            "codex",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["runtime"]["ok"] is True
    assert payload["status"]["ok"] is True
    assert raw_secret not in captured.out
    assert "[redacted]" in payload["runtime"]["stdout"]
