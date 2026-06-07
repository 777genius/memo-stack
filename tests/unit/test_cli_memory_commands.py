from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from memo_stack_cli import cli
from memo_stack_cli.config import init_local_config


class FakeMemoStackClient:
    instances: list[FakeMemoStackClient] = []

    def __init__(self, *, base_url: str, token: str, **_kwargs: Any) -> None:
        self.base_url = base_url
        self.token = token
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.instances.append(self)

    def build_insights(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("build_insights", kwargs))
        return {
            "data": {
                "insights_id": "ins_cli",
                "health_score": 91.5,
                "metrics": {
                    "facts": {"expired_active": 1},
                    "documents": {"without_chunks": 2},
                    "suggestions": {"pending": 3},
                },
                "action_items": [{"id": "mai_1"}],
            }
        }

    def export_profile_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("export_profile_snapshot", kwargs))
        return {
            "data": {
                "schema_version": 1,
                "space": {"slug": kwargs["space_slug"]},
                "profile": {"external_ref": kwargs["profile_external_ref"]},
                "facts": [{"id": "fact_1", "text": None if kwargs["redacted"] else "raw"}],
                "redacted": kwargs["redacted"],
            },
            "status": "ok",
        }

    def import_profile_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("import_profile_snapshot", kwargs))
        return {
            "data": {
                "status": "ok",
                "dry_run": kwargs["dry_run"],
                "merge_strategy": kwargs["merge_strategy"],
            }
        }


def test_cli_insights_prints_summary_and_uses_default_scope(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _configure(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "MemoStackClient", FakeMemoStackClient)
    FakeMemoStackClient.instances.clear()

    exit_code = cli.main(["insights"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "health_score: 91.5" in captured.out
    assert "pending_suggestions: 3" in captured.out
    call_name, kwargs = FakeMemoStackClient.instances[0].calls[0]
    assert call_name == "build_insights"
    assert kwargs["scope"].space_slug == "default"
    assert kwargs["scope"].profile_external_ref == "default"


def test_cli_profile_export_is_redacted_by_default(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _configure(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "MemoStackClient", FakeMemoStackClient)
    FakeMemoStackClient.instances.clear()
    out_path = tmp_path / "snapshot.json"

    exit_code = cli.main(["profile-export", "--out", str(out_path)])

    captured = capsys.readouterr()
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert str(out_path) in captured.out
    assert written["redacted"] is True
    assert written["facts"][0]["text"] is None
    call_name, kwargs = FakeMemoStackClient.instances[0].calls[0]
    assert call_name == "export_profile_snapshot"
    assert kwargs["redacted"] is True


def test_cli_profile_import_dry_run_and_apply_confirmation(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _configure(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "MemoStackClient", FakeMemoStackClient)
    FakeMemoStackClient.instances.clear()
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

    dry_run_exit = cli.main(["profile-import", "--in", str(snapshot_path)])
    rejected_exit = cli.main(["profile-import", "--in", str(snapshot_path), "--apply"])
    apply_exit = cli.main(
        ["profile-import", "--in", str(snapshot_path), "--apply", "--confirmed"]
    )

    captured = capsys.readouterr()
    assert dry_run_exit == 0
    assert rejected_exit == 1
    assert apply_exit == 0
    assert "requires --confirmed" in captured.err
    first_call = FakeMemoStackClient.instances[0].calls[0]
    second_call = FakeMemoStackClient.instances[1].calls[0]
    assert first_call[0] == "import_profile_snapshot"
    assert first_call[1]["dry_run"] is True
    assert second_call[1]["dry_run"] is False
    assert second_call[1]["confirmed"] is True


def _configure(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    init_local_config(home=home, repo_dir=repo)
    monkeypatch.setenv("MEMO_STACK_HOME", str(home))
