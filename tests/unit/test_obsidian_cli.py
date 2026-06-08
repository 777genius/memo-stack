from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from memo_stack_obsidian import cli, doctor
from memo_stack_obsidian.conflicts import WriteConflictArtifactsUseCase
from memo_stack_obsidian.note_format import FACTS_DIR, TEXT_END, TEXT_START
from memo_stack_obsidian.setup import SETUP_README, SetupVaultUseCase
from memo_stack_obsidian.state import SqliteSyncStateStore
from memo_stack_obsidian.sync import (
    INBOX_DIR,
    ExportFactsToVaultUseCase,
    ImportInboxSuggestionsUseCase,
    ImportVaultChangesUseCase,
    PreviewVaultSyncUseCase,
    SyncVaultOnceUseCase,
)
from memo_stack_obsidian.vault import FilesystemVault


def test_cli_connect_preview_export_import_dry_run_smoke(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    gateway = FakeMemoryGateway()
    monkeypatch.setattr(cli, "_context", context_factory(tmp_path, gateway))
    common = ["--vault", str(tmp_path), "--space", "default", "--profile", "me", "--json"]

    assert cli.main(["connect", *common]) == 0
    connect_payload = read_json(capsys)
    assert connect_payload["ok"] is True
    assert (tmp_path / SETUP_README).exists()

    assert cli.main(["preview", *common]) == 0
    preview_payload = read_json(capsys)
    assert preview_payload["export"]["would_export"] == 1
    assert preview_payload["import"]["would_suggest"] == 0

    assert cli.main(["export", *common]) == 0
    export_payload = read_json(capsys)
    assert export_payload["exported"] == 1
    fact_path = tmp_path / FACTS_DIR / "fact_123.md"
    assert fact_path.exists()

    replace_managed_text(fact_path, "Use Graphiti for temporal graph recall.")
    assert cli.main(["import", *common]) == 0
    import_payload = read_json(capsys)
    assert import_payload["would_update"] == 1
    assert gateway.update_calls == []

    assert cli.main(["sync", *common]) == 1
    dry_sync_payload = read_json(capsys)
    assert dry_sync_payload["export_skipped"] is True
    assert dry_sync_payload["import"]["would_update"] == 1

    assert cli.main(["sync", *common, "--apply-import"]) == 0
    sync_payload = read_json(capsys)
    assert sync_payload["ok"] is True
    assert sync_payload["import"]["updated"] == 1
    assert sync_payload["export"]["exported"] == 1
    assert len(gateway.update_calls) == 1


def test_cli_install_plugin_copies_bundle_into_vault(
    tmp_path: Path,
    capsys: Any,
) -> None:
    assert cli.main(["install-plugin", "--vault", str(tmp_path), "--json"]) == 0
    payload = read_json(capsys)
    plugin_dir = tmp_path / ".obsidian/plugins/memo-stack"

    assert payload["ok"] is True
    assert payload["target_dir"] == str(plugin_dir.resolve())
    assert (plugin_dir / "manifest.json").exists()
    assert (plugin_dir / "main.js").exists()
    assert (plugin_dir / "styles.css").exists()
    settings = json.loads((plugin_dir / "data.json").read_text(encoding="utf-8"))
    assert settings["vaultPathOverride"] == str(tmp_path.resolve())
    assert settings["localCliPath"] == "memo-stack"

    assert cli.main(["install-plugin", "--vault", str(tmp_path), "--json"]) == 0
    second_payload = read_json(capsys)
    assert len(second_payload["skipped"]) == 4


def test_cli_install_plugin_can_enable_and_configure_plugin(
    tmp_path: Path,
    capsys: Any,
) -> None:
    assert (
        cli.main(
            [
                "install-plugin",
                "--vault",
                str(tmp_path),
                "--enable",
                "--api-url",
                "http://127.0.0.1:17788",
                "--space",
                "team",
                "--profile",
                "backend",
                "--apply-import",
                "--local-cli-path",
                "/usr/local/bin/memo-stack",
                "--json",
            ]
        )
        == 0
    )
    payload = read_json(capsys)
    plugin_dir = tmp_path / ".obsidian/plugins/memo-stack"
    enabled = json.loads(
        (tmp_path / ".obsidian/community-plugins.json").read_text(encoding="utf-8")
    )
    settings = json.loads((plugin_dir / "data.json").read_text(encoding="utf-8"))

    assert payload["enabled"] is True
    assert enabled == ["memo-stack"]
    assert settings["apiUrl"] == "http://127.0.0.1:17788"
    assert settings["spaceSlug"] == "team"
    assert settings["profileExternalRef"] == "backend"
    assert settings["applyImportOnSync"] is True
    assert settings["localCliPath"] == "/usr/local/bin/memo-stack"


def test_cli_doctor_reports_ready_vault_without_opening_obsidian(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    SetupVaultUseCase(vault=FilesystemVault(tmp_path)).execute(
        space_slug="team",
        profile_external_ref="backend",
    )
    assert (
        cli.main(
            [
                "install-plugin",
                "--vault",
                str(tmp_path),
                "--enable",
                "--api-url",
                "http://127.0.0.1:17788",
                "--space",
                "team",
                "--profile",
                "backend",
                "--json",
            ]
        )
        == 0
    )
    read_json(capsys)
    monkeypatch.setattr(doctor.httpx, "get", fake_health_get)

    assert (
        cli.main(
            [
                "doctor",
                "--vault",
                str(tmp_path),
                "--api-url",
                "http://127.0.0.1:17788",
                "--space",
                "team",
                "--profile",
                "backend",
                "--json",
            ]
        )
        == 0
    )
    payload = read_json(capsys)

    assert payload["ok"] is True
    assert {check["name"] for check in payload["checks"]} >= {
        "vault_exists",
        "plugin_installed",
        "plugin_enabled",
        "plugin_settings",
        "backend_health",
    }
    assert all(check["ok"] for check in payload["checks"])


def test_cli_doctor_reports_missing_plugin_without_health_call(
    tmp_path: Path,
    capsys: Any,
) -> None:
    SetupVaultUseCase(vault=FilesystemVault(tmp_path)).execute(
        space_slug="default",
        profile_external_ref="me",
    )

    assert (
        cli.main(
            [
                "doctor",
                "--vault",
                str(tmp_path),
                "--space",
                "default",
                "--profile",
                "me",
                "--no-health",
                "--json",
            ]
        )
        == 1
    )
    payload = read_json(capsys)
    checks = {check["name"]: check for check in payload["checks"]}

    assert payload["ok"] is False
    assert checks["plugin_installed"]["ok"] is False


def test_cli_watch_runs_one_loop_without_opening_obsidian(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    gateway = FakeMemoryGateway()
    monkeypatch.setattr(cli, "_context", context_factory(tmp_path, gateway))
    write_inbox_note(tmp_path, "Remember that watch imports inbox without Obsidian UI.")
    sleeps: list[float] = []

    def stop_after_first_sleep(interval: float) -> None:
        sleeps.append(interval)
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.time, "sleep", stop_after_first_sleep)

    result = cli.main(
        [
            "watch",
            "--vault",
            str(tmp_path),
            "--space",
            "default",
            "--profile",
            "me",
            "--apply-import",
            "--interval",
            "0.5",
            "--export-every",
            "1",
        ]
    )
    captured = capsys.readouterr()

    assert result == 130
    assert sleeps == [0.5]
    assert "memo-stack-obsidian: watching vault." in captured.out
    assert (
        "import updated=0 would_update=0 suggested=1 would_suggest=0 "
        "conflicts=0 conflict_artifacts=0"
    ) in captured.out
    assert "export exported=1 skipped=0 conflicts=0 conflict_artifacts=0" in captured.out
    assert captured.err == "Interrupted.\n"
    assert len(gateway.suggestion_calls) == 1
    assert (tmp_path / FACTS_DIR / "fact_123.md").exists()


def context_factory(tmp_path: Path, gateway: FakeMemoryGateway) -> Any:
    def _context(args: Any) -> dict[str, object]:
        vault = FilesystemVault(args.vault)
        state = SqliteSyncStateStore(tmp_path / ".memo-stack" / "obsidian-sync.sqlite3")
        exporter = ExportFactsToVaultUseCase(memory=gateway, vault=vault, state=state)
        importer = ImportVaultChangesUseCase(memory=gateway, vault=vault, state=state)
        inbox_importer = ImportInboxSuggestionsUseCase(
            memory=gateway,
            vault=vault,
            state=state,
        )
        return {
            "setup": SetupVaultUseCase(vault=vault),
            "exporter": exporter,
            "importer": importer,
            "inbox_importer": inbox_importer,
            "previewer": PreviewVaultSyncUseCase(memory=gateway, vault=vault, state=state),
            "syncer": SyncVaultOnceUseCase(
                importer=importer,
                inbox_importer=inbox_importer,
                exporter=exporter,
            ),
            "conflict_writer": WriteConflictArtifactsUseCase(vault=vault),
        }

    return _context


def read_json(capsys: Any) -> dict[str, object]:
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def replace_managed_text(path: Path, new_text: str) -> None:
    old = path.read_text(encoding="utf-8")
    start = old.index(TEXT_START) + len(TEXT_START)
    end = old.index(TEXT_END)
    path.write_text(old[:start] + f"\n{new_text}\n" + old[end:], encoding="utf-8")


def write_inbox_note(tmp_path: Path, text: str) -> None:
    path = tmp_path / INBOX_DIR / "idea.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def fake_health_get(*args: Any, **kwargs: Any) -> Any:
    class Response:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

    return Response()


class FakeMemoryGateway:
    def __init__(self) -> None:
        self.fact = {
            "id": "fact_123",
            "space_id": "space_1",
            "profile_id": "profile_1",
            "thread_id": None,
            "text": "Use Qdrant for document recall.",
            "kind": "architecture_decision",
            "status": "active",
            "version": 1,
            "confidence": "high",
            "trust_level": "high",
            "classification": "internal",
            "category": "retrieval",
            "tags": [],
            "ttl_policy": None,
            "expires_at": None,
            "source_refs": [{"source_type": "manual", "source_id": "test"}],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        self.update_calls: list[dict[str, object]] = []
        self.suggestion_calls: list[dict[str, object]] = []

    def list_facts(
        self,
        *,
        space_slug: str,
        profile_external_ref: str,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, object]:
        return {"data": [deepcopy(self.fact)], "next_cursor": None}

    def get_fact(self, fact_id: str) -> dict[str, object]:
        assert fact_id == self.fact["id"]
        return {"data": deepcopy(self.fact)}

    def update_fact(
        self,
        fact_id: str,
        *,
        expected_version: int,
        text: str,
        reason: str,
        source_refs: list[dict[str, object]],
    ) -> dict[str, object]:
        assert fact_id == self.fact["id"]
        assert expected_version == self.fact["version"]
        self.update_calls.append(
            {
                "fact_id": fact_id,
                "expected_version": expected_version,
                "text": text,
                "reason": reason,
                "source_refs": source_refs,
            }
        )
        self.fact["text"] = text
        self.fact["version"] = int(self.fact["version"]) + 1
        self.fact["source_refs"] = source_refs
        return {"data": deepcopy(self.fact)}

    def create_suggestion(
        self,
        *,
        space_slug: str,
        profile_external_ref: str,
        candidate_text: str,
        safe_reason: str,
        source_refs: list[dict[str, object]],
        candidate_fingerprint: str | None = None,
    ) -> dict[str, object]:
        call = {
            "space_slug": space_slug,
            "profile_external_ref": profile_external_ref,
            "candidate_text": candidate_text,
            "safe_reason": safe_reason,
            "source_refs": source_refs,
            "candidate_fingerprint": candidate_fingerprint,
        }
        self.suggestion_calls.append(call)
        return {"data": {"id": "sug_1", **call}}
