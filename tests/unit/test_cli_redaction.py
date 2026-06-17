from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from memo_stack_cli import cli
from memo_stack_cli.config import init_local_config
from memo_stack_cli.runtime import RuntimeResult


def test_cli_top_level_errors_are_redacted(monkeypatch, capsys) -> None:
    raw_secret = "sk-proj-secretvalue1234567890"

    def fail_load_config() -> Any:
        raise ValueError(f"provider failed with {raw_secret}")

    monkeypatch.setattr(cli, "load_config", fail_load_config)

    exit_code = cli.main(["status"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert raw_secret not in captured.err
    assert "[redacted]" in captured.err


def test_cli_runtime_output_is_redacted(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    raw_secret = "sk-proj-secretvalue1234567890"
    _configure(tmp_path, monkeypatch)

    class FakeRuntime:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def logs(self, _service: str | None, _tail: int) -> RuntimeResult:
            return RuntimeResult(
                ok=False,
                command=("docker", "compose", "logs"),
                returncode=1,
                stdout=f"stdout before {raw_secret}\nstdout after\n",
                stderr=f"stderr before Bearer {raw_secret}\nstderr after\n",
            )

    monkeypatch.setattr(cli, "DockerComposeRuntime", FakeRuntime)

    exit_code = cli.main(["logs"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert raw_secret not in captured.out
    assert raw_secret not in captured.err
    assert "stdout after\n" in captured.out
    assert "stderr after\n" in captured.err
    assert "[redacted]" in captured.out
    assert "[redacted]" in captured.err


def test_cli_non_json_response_body_is_redacted() -> None:
    raw_secret = "sk-proj-secretvalue1234567890"
    response = httpx.Response(502, text=f"upstream leaked Bearer {raw_secret}")

    payload = cli._response_payload(response)

    body = payload["data"]["body"]
    assert raw_secret not in body
    assert "[redacted]" in body


def _configure(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    init_local_config(home=home, repo_dir=repo)
    monkeypatch.setenv("MEMO_STACK_HOME", str(home))
