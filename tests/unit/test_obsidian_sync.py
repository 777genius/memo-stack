from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from memo_stack_obsidian.conflicts import CONFLICTS_DIR, WriteConflictArtifactsUseCase
from memo_stack_obsidian.domain import ExportStatus, ImportStatus
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


def test_setup_vault_writes_onboarding_notes(tmp_path: Path) -> None:
    setup = SetupVaultUseCase(vault=FilesystemVault(tmp_path))

    result = setup.execute(space_slug="default", profile_external_ref="me")
    readme = (tmp_path / SETUP_README).read_text(encoding="utf-8")

    assert str(SETUP_README) in result.written
    assert "- Space: `default`" in readme
    assert "- Profile: `me`" in readme
    assert (tmp_path / INBOX_DIR / "README.md").exists()
    assert (tmp_path / CONFLICTS_DIR / "README.md").exists()
    assert (tmp_path / FACTS_DIR / ".gitkeep.md").exists()


def test_setup_vault_does_not_overwrite_existing_notes_by_default(tmp_path: Path) -> None:
    setup = SetupVaultUseCase(vault=FilesystemVault(tmp_path))
    setup.execute(space_slug="default", profile_external_ref="me")
    readme_path = tmp_path / SETUP_README
    readme_path.write_text("Custom local readme", encoding="utf-8")

    result = setup.execute(space_slug="default", profile_external_ref="me")

    assert str(SETUP_README) in result.skipped
    assert readme_path.read_text(encoding="utf-8") == "Custom local readme"


def test_import_skips_setup_helper_note_in_generated_facts(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    setup = SetupVaultUseCase(vault=FilesystemVault(tmp_path))
    _exporter, importer = use_cases(tmp_path, gateway)
    setup.execute(space_slug="default", profile_external_ref="me")

    imported = importer.execute(apply=False)

    assert imported.changes == ()


def test_inbox_import_skips_setup_readme(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    setup = SetupVaultUseCase(vault=FilesystemVault(tmp_path))
    importer = inbox_importer(tmp_path, gateway)
    setup.execute(space_slug="default", profile_external_ref="me")

    imported = importer.execute(space_slug="default", profile_external_ref="me", apply=True)

    assert imported.changes == ()
    assert gateway.suggestion_calls == []


def test_export_then_import_unchanged_fact(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    exporter, importer = use_cases(tmp_path, gateway)

    exported = exporter.execute(space_slug="default", profile_external_ref="me")
    imported = importer.execute(apply=False)

    assert exported.exported == 1
    assert imported.changes[0].status == ImportStatus.UNCHANGED


def test_preview_empty_vault_reports_would_export_without_writing(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    previewer = previewer_use_case(tmp_path, gateway)

    result = previewer.execute(space_slug="default", profile_external_ref="me")

    assert result.ok is True
    assert result.export_plan.would_export == 1
    assert result.export_plan.changes[0].status == ExportStatus.WOULD_EXPORT
    assert not (tmp_path / FACTS_DIR / "fact_123.md").exists()


def test_preview_clean_exported_fact_is_skipped(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    exporter, _importer = use_cases(tmp_path, gateway)
    previewer = previewer_use_case(tmp_path, gateway)
    exporter.execute(space_slug="default", profile_external_ref="me")

    result = previewer.execute(space_slug="default", profile_external_ref="me")

    assert result.export_plan.skipped == 1
    assert result.export_plan.changes[0].status == ExportStatus.SKIPPED


def test_import_dry_run_reports_direct_update(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    exporter, importer = use_cases(tmp_path, gateway)
    exporter.execute(space_slug="default", profile_external_ref="me")
    replace_managed_text(tmp_path, "Use Graphiti for temporal graph recall.")

    imported = importer.execute(apply=False)

    assert imported.would_update == 1
    assert gateway.update_calls == []
    assert imported.changes[0].status == ImportStatus.WOULD_UPDATE


def test_export_does_not_overwrite_unimported_local_edit(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    exporter, _importer = use_cases(tmp_path, gateway)
    exporter.execute(space_slug="default", profile_external_ref="me")
    replace_managed_text(tmp_path, "Local edit that should survive.")
    gateway.fact["text"] = "Backend changed while local edit is pending."
    gateway.fact["version"] = 2

    exported = exporter.execute(space_slug="default", profile_external_ref="me")
    note_text = next((tmp_path / FACTS_DIR).glob("*.md")).read_text(encoding="utf-8")

    assert exported.conflicts == 1
    assert exported.changes[0].status == ExportStatus.CONFLICT
    assert "unimported local edits" in exported.changes[0].message
    assert "Local edit that should survive." in note_text
    assert "Backend changed while local edit is pending." not in note_text


def test_preview_reports_dirty_managed_note_conflict(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    exporter, _importer = use_cases(tmp_path, gateway)
    previewer = previewer_use_case(tmp_path, gateway)
    exporter.execute(space_slug="default", profile_external_ref="me")
    replace_managed_text(tmp_path, "Local edit that should survive.")

    result = previewer.execute(space_slug="default", profile_external_ref="me")

    assert result.ok is False
    assert result.export_plan.conflicts == 1
    assert result.import_plan.would_update == 1


def test_sync_once_skips_export_when_dry_run_direct_update_is_pending(
    tmp_path: Path,
) -> None:
    gateway = FakeMemoryGateway()
    exporter, _importer = use_cases(tmp_path, gateway)
    syncer = syncer_use_case(tmp_path, gateway)
    exporter.execute(space_slug="default", profile_external_ref="me")
    replace_managed_text(tmp_path, "Local edit that should not be overwritten.")
    gateway.fact["text"] = "Backend refresh that must wait."

    result = syncer.execute(
        space_slug="default",
        profile_external_ref="me",
        apply_import=False,
    )
    note_text = next((tmp_path / FACTS_DIR).glob("*.md")).read_text(encoding="utf-8")

    assert result.ok is False
    assert result.export_skipped is True
    assert result.import_result.conflicts == 0
    assert result.import_result.would_update == 1
    assert result.export_result.changes == ()
    assert "Local edit that should not be overwritten." in note_text
    assert "Backend refresh that must wait." not in note_text


def test_sync_once_apply_import_then_exports_clean_backend_projection(
    tmp_path: Path,
) -> None:
    gateway = FakeMemoryGateway()
    exporter, _importer = use_cases(tmp_path, gateway)
    syncer = syncer_use_case(tmp_path, gateway)
    exporter.execute(space_slug="default", profile_external_ref="me")
    replace_managed_text(tmp_path, "Use Graphiti for temporal graph recall.")

    result = syncer.execute(
        space_slug="default",
        profile_external_ref="me",
        apply_import=True,
    )
    note_text = next((tmp_path / FACTS_DIR).glob("*.md")).read_text(encoding="utf-8")

    assert result.ok is True
    assert result.import_result.updated == 1
    assert result.export_result.exported == 1
    assert "Use Graphiti for temporal graph recall." in note_text
    assert "memo_stack_version: 2" in note_text


def test_deleted_generated_fact_is_recreated_on_next_export(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    exporter, _importer = use_cases(tmp_path, gateway)
    exporter.execute(space_slug="default", profile_external_ref="me")
    fact_path = tmp_path / FACTS_DIR / "fact_123.md"
    fact_path.unlink()

    exported = exporter.execute(space_slug="default", profile_external_ref="me")

    assert exported.exported == 1
    assert fact_path.exists()
    assert "Use Qdrant for document recall." in fact_path.read_text(encoding="utf-8")


def test_sync_once_conflicts_on_renamed_generated_note_without_creating_duplicate(
    tmp_path: Path,
) -> None:
    gateway = FakeMemoryGateway()
    exporter, _importer = use_cases(tmp_path, gateway)
    syncer = syncer_use_case(tmp_path, gateway)
    exporter.execute(space_slug="default", profile_external_ref="me")
    fact_path = tmp_path / FACTS_DIR / "fact_123.md"
    renamed_path = tmp_path / FACTS_DIR / "renamed-fact.md"
    fact_path.rename(renamed_path)

    result = syncer.execute(
        space_slug="default",
        profile_external_ref="me",
        apply_import=True,
    )

    assert result.ok is False
    assert result.import_result.conflicts == 0
    assert result.export_result.conflicts == 1
    assert "non-canonical path" in result.export_result.changes[0].message
    assert result.export_result.changes[0].path.as_posix().endswith("renamed-fact.md")
    assert not fact_path.exists()
    assert len(list((tmp_path / FACTS_DIR).glob("*.md"))) == 1


def test_sync_once_removes_clean_generated_note_when_backend_fact_is_deleted(
    tmp_path: Path,
) -> None:
    gateway = FakeMemoryGateway()
    exporter, _importer = use_cases(tmp_path, gateway)
    syncer = syncer_use_case(tmp_path, gateway)
    exporter.execute(space_slug="default", profile_external_ref="me")
    fact_path = tmp_path / FACTS_DIR / "fact_123.md"
    gateway.fact["status"] = "deleted"
    gateway.fact["version"] = 2

    result = syncer.execute(
        space_slug="default",
        profile_external_ref="me",
        apply_import=True,
    )

    assert result.ok is True
    assert result.import_result.removed == 1
    assert result.import_result.changes[0].status == ImportStatus.REMOVED
    assert not fact_path.exists()
    assert result.export_result.changes == ()


def test_sync_once_keeps_dirty_generated_note_when_backend_fact_is_deleted(
    tmp_path: Path,
) -> None:
    gateway = FakeMemoryGateway()
    exporter, _importer = use_cases(tmp_path, gateway)
    syncer = syncer_use_case(tmp_path, gateway)
    exporter.execute(space_slug="default", profile_external_ref="me")
    fact_path = tmp_path / FACTS_DIR / "fact_123.md"
    replace_managed_text(tmp_path, "Local delete-race edit must survive.")
    gateway.fact["status"] = "deleted"
    gateway.fact["version"] = 2

    result = syncer.execute(
        space_slug="default",
        profile_external_ref="me",
        apply_import=True,
    )

    assert result.ok is False
    assert result.export_skipped is True
    assert result.import_result.conflicts == 1
    assert result.import_result.changes[0].status == ImportStatus.CONFLICT
    assert "Stale version" in result.import_result.changes[0].message
    assert "Local delete-race edit must survive." in fact_path.read_text(encoding="utf-8")


def test_sync_once_skips_export_when_managed_note_is_corrupt(
    tmp_path: Path,
) -> None:
    gateway = FakeMemoryGateway()
    exporter, _importer = use_cases(tmp_path, gateway)
    syncer = syncer_use_case(tmp_path, gateway)
    exporter.execute(space_slug="default", profile_external_ref="me")
    fact_path = tmp_path / FACTS_DIR / "fact_123.md"
    fact_path.write_text("not a memo stack fact note", encoding="utf-8")
    gateway.fact["text"] = "Backend text that must not overwrite corrupt note."
    gateway.fact["version"] = 2

    result = syncer.execute(
        space_slug="default",
        profile_external_ref="me",
        apply_import=True,
    )

    assert result.ok is False
    assert result.export_skipped is True
    assert result.import_result.conflicts == 1
    assert result.export_result.changes == ()
    assert fact_path.read_text(encoding="utf-8") == "not a memo stack fact note"


def test_import_detects_duplicate_fact_id_and_sync_skips_export(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    exporter, _importer = use_cases(tmp_path, gateway)
    syncer = syncer_use_case(tmp_path, gateway)
    exporter.execute(space_slug="default", profile_external_ref="me")
    original = tmp_path / FACTS_DIR / "fact_123.md"
    duplicate = tmp_path / FACTS_DIR / "zzz-duplicate.md"
    duplicate.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")

    result = syncer.execute(
        space_slug="default",
        profile_external_ref="me",
        apply_import=True,
    )

    assert result.ok is False
    assert result.export_skipped is True
    assert result.import_result.conflicts == 1
    assert result.import_result.changes[-1].status == ImportStatus.CONFLICT
    assert "Duplicate memo_stack_id" in result.import_result.changes[-1].message


def test_export_conflict_writes_obsidian_visible_artifact(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    exporter, _importer = use_cases(tmp_path, gateway)
    conflict_writer = WriteConflictArtifactsUseCase(vault=FilesystemVault(tmp_path))
    exporter.execute(space_slug="default", profile_external_ref="me")
    replace_managed_text(tmp_path, "Local edit that should survive.")

    exported = exporter.execute(space_slug="default", profile_external_ref="me")
    artifacts = conflict_writer.execute(direction="export", changes=exported.changes)
    artifact_text = next((tmp_path / CONFLICTS_DIR).glob("*.md")).read_text(encoding="utf-8")

    assert artifacts.written == 1
    assert "Memo Stack Sync Conflict" in artifact_text
    assert "unimported local edits" in artifact_text


def test_import_apply_updates_backend_and_rewrites_note_version(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    exporter, importer = use_cases(tmp_path, gateway)
    exporter.execute(space_slug="default", profile_external_ref="me")
    replace_managed_text(tmp_path, "Use Graphiti for temporal graph recall.")

    imported = importer.execute(apply=True)
    note_text = next((tmp_path / FACTS_DIR).glob("*.md")).read_text(encoding="utf-8")

    assert imported.updated == 1
    assert gateway.fact["text"] == "Use Graphiti for temporal graph recall."
    assert gateway.fact["version"] == 2
    assert gateway.fact["source_refs"][0]["source_type"] == "manual"
    assert gateway.fact["source_refs"][1]["source_type"] == "obsidian"
    assert "memo_stack_version: 2" in note_text
    assert imported.changes[0].status == ImportStatus.UPDATED


def test_import_detects_stale_backend_version(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    exporter, importer = use_cases(tmp_path, gateway)
    exporter.execute(space_slug="default", profile_external_ref="me")
    gateway.fact["version"] = 2
    replace_managed_text(tmp_path, "Stale local edit.")

    imported = importer.execute(apply=True)

    assert imported.conflicts == 1
    assert imported.changes[0].status == ImportStatus.CONFLICT
    assert "Stale version" in imported.changes[0].message


def test_import_conflict_writes_obsidian_visible_artifact(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    exporter, importer = use_cases(tmp_path, gateway)
    conflict_writer = WriteConflictArtifactsUseCase(vault=FilesystemVault(tmp_path))
    exporter.execute(space_slug="default", profile_external_ref="me")
    gateway.fact["version"] = 2
    replace_managed_text(tmp_path, "Stale local edit.")

    imported = importer.execute(apply=True)
    artifacts = conflict_writer.execute(direction="import", changes=imported.changes)
    artifact_text = next((tmp_path / CONFLICTS_DIR).glob("*.md")).read_text(encoding="utf-8")

    assert artifacts.written == 1
    assert "Memo Stack Sync Conflict" in artifact_text
    assert "Stale version" in artifact_text


def test_inbox_import_dry_run_reports_pending_suggestion(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    importer = inbox_importer(tmp_path, gateway)
    write_inbox_note(tmp_path, "Remember that Obsidian inbox notes become suggestions.")

    imported = importer.execute(space_slug="default", profile_external_ref="me", apply=False)

    assert imported.would_suggest == 1
    assert imported.changes[0].status == ImportStatus.WOULD_SUGGEST
    assert gateway.suggestion_calls == []


def test_preview_reports_inbox_would_suggest_without_api_side_effect(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    previewer = previewer_use_case(tmp_path, gateway)
    write_inbox_note(tmp_path, "Remember that preview should not create suggestions.")

    result = previewer.execute(space_slug="default", profile_external_ref="me")

    assert result.import_plan.would_suggest == 1
    assert gateway.suggestion_calls == []


def test_inbox_import_apply_creates_suggestion_once_for_same_hash(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    importer = inbox_importer(tmp_path, gateway)
    write_inbox_note(tmp_path, "Remember that Obsidian inbox notes become suggestions.")

    first = importer.execute(space_slug="default", profile_external_ref="me", apply=True)
    second = importer.execute(space_slug="default", profile_external_ref="me", apply=True)

    assert first.suggested == 1
    assert second.changes[0].status == ImportStatus.UNCHANGED
    assert len(gateway.suggestion_calls) == 1
    assert gateway.suggestion_calls[0]["candidate_text"].startswith("Remember")


def test_inbox_import_rejects_oversized_note(tmp_path: Path) -> None:
    gateway = FakeMemoryGateway()
    importer = inbox_importer(tmp_path, gateway)
    write_inbox_note(tmp_path, "x" * 4001)

    imported = importer.execute(space_slug="default", profile_external_ref="me", apply=True)

    assert imported.conflicts == 1
    assert imported.changes[0].status == ImportStatus.CONFLICT
    assert "too large" in imported.changes[0].message
    assert gateway.suggestion_calls == []


def use_cases(
    tmp_path: Path,
    gateway: FakeMemoryGateway,
) -> tuple[ExportFactsToVaultUseCase, ImportVaultChangesUseCase]:
    vault = FilesystemVault(tmp_path)
    state = SqliteSyncStateStore(tmp_path / ".memo-stack" / "obsidian-sync.sqlite3")
    return (
        ExportFactsToVaultUseCase(memory=gateway, vault=vault, state=state),
        ImportVaultChangesUseCase(memory=gateway, vault=vault, state=state),
    )


def inbox_importer(tmp_path: Path, gateway: FakeMemoryGateway) -> ImportInboxSuggestionsUseCase:
    return ImportInboxSuggestionsUseCase(
        memory=gateway,
        vault=FilesystemVault(tmp_path),
        state=SqliteSyncStateStore(tmp_path / ".memo-stack" / "obsidian-sync.sqlite3"),
    )


def previewer_use_case(tmp_path: Path, gateway: FakeMemoryGateway) -> PreviewVaultSyncUseCase:
    return PreviewVaultSyncUseCase(
        memory=gateway,
        vault=FilesystemVault(tmp_path),
        state=SqliteSyncStateStore(tmp_path / ".memo-stack" / "obsidian-sync.sqlite3"),
    )


def syncer_use_case(tmp_path: Path, gateway: FakeMemoryGateway) -> SyncVaultOnceUseCase:
    vault = FilesystemVault(tmp_path)
    state = SqliteSyncStateStore(tmp_path / ".memo-stack" / "obsidian-sync.sqlite3")
    return SyncVaultOnceUseCase(
        importer=ImportVaultChangesUseCase(memory=gateway, vault=vault, state=state),
        inbox_importer=ImportInboxSuggestionsUseCase(
            memory=gateway,
            vault=vault,
            state=state,
        ),
        exporter=ExportFactsToVaultUseCase(memory=gateway, vault=vault, state=state),
    )


def replace_managed_text(tmp_path: Path, new_text: str) -> None:
    path = next((tmp_path / FACTS_DIR).glob("*.md"))
    old = path.read_text(encoding="utf-8")
    start = old.index(TEXT_START) + len(TEXT_START)
    end = old.index(TEXT_END)
    path.write_text(old[:start] + f"\n{new_text}\n" + old[end:], encoding="utf-8")


def write_inbox_note(tmp_path: Path, text: str) -> None:
    path = tmp_path / INBOX_DIR / "idea.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
        if self.fact["status"] != "active":
            return {"data": [], "next_cursor": None}
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
