"""Obsidian connector application use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from memo_stack_obsidian.domain import (
    ExportChange,
    ExportStatus,
    ImportChange,
    ImportStatus,
    NoteKind,
    SyncMode,
    SyncStateRecord,
    content_hash,
)
from memo_stack_obsidian.frontmatter import FrontmatterError, split_frontmatter
from memo_stack_obsidian.layout import DEFAULT_ROOT_FOLDER, ObsidianVaultLayout
from memo_stack_obsidian.note_format import (
    NoteFormatError,
    fact_note_path,
    parse_fact_note,
    render_fact_note,
    state_record_for_note,
)
from memo_stack_obsidian.ports import MemoryGatewayPort, SyncStateStorePort, VaultPort

INBOX_DIR = PurePosixPath(f"{DEFAULT_ROOT_FOLDER}/inbox")
MAX_INBOX_SUGGESTION_CHARS = 4000


@dataclass(frozen=True)
class ExportFactsResult:
    changes: tuple[ExportChange, ...] = ()

    @property
    def exported(self) -> int:
        return sum(1 for change in self.changes if change.status == ExportStatus.EXPORTED)

    @property
    def conflicts(self) -> int:
        return sum(1 for change in self.changes if change.status == ExportStatus.CONFLICT)

    @property
    def skipped(self) -> int:
        return sum(1 for change in self.changes if change.status == ExportStatus.SKIPPED)

    @property
    def would_export(self) -> int:
        return sum(1 for change in self.changes if change.status == ExportStatus.WOULD_EXPORT)

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(change.path.as_posix() for change in self.changes)


@dataclass(frozen=True)
class ImportVaultChangesResult:
    changes: tuple[ImportChange, ...] = ()

    @property
    def updated(self) -> int:
        return sum(1 for change in self.changes if change.status == ImportStatus.UPDATED)

    @property
    def removed(self) -> int:
        return sum(1 for change in self.changes if change.status == ImportStatus.REMOVED)

    @property
    def conflicts(self) -> int:
        return sum(1 for change in self.changes if change.status == ImportStatus.CONFLICT)

    @property
    def would_update(self) -> int:
        return sum(1 for change in self.changes if change.status == ImportStatus.WOULD_UPDATE)

    @property
    def would_suggest(self) -> int:
        return sum(1 for change in self.changes if change.status == ImportStatus.WOULD_SUGGEST)

    @property
    def suggested(self) -> int:
        return sum(1 for change in self.changes if change.status == ImportStatus.SUGGESTED)


@dataclass(frozen=True)
class PreviewVaultSyncResult:
    export_plan: ExportFactsResult
    import_plan: ImportVaultChangesResult

    @property
    def ok(self) -> bool:
        return self.export_plan.conflicts == 0 and self.import_plan.conflicts == 0


@dataclass(frozen=True)
class SyncVaultOnceResult:
    import_result: ImportVaultChangesResult
    export_result: ExportFactsResult = field(default_factory=ExportFactsResult)
    export_skipped_reason: str = ""

    @property
    def export_skipped(self) -> bool:
        return bool(self.export_skipped_reason)

    @property
    def conflicts(self) -> int:
        return self.import_result.conflicts + self.export_result.conflicts

    @property
    def ok(self) -> bool:
        return self.conflicts == 0 and not self.export_skipped


@dataclass
class ExportFactsToVaultUseCase:
    memory: MemoryGatewayPort
    vault: VaultPort
    state: SyncStateStorePort
    layout: ObsidianVaultLayout = field(default_factory=ObsidianVaultLayout)

    def execute(
        self,
        *,
        space_slug: str,
        profile_external_ref: str,
        limit: int = 100,
    ) -> ExportFactsResult:
        changes: list[ExportChange] = []
        for fact in _iter_facts(
            self.memory,
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
            limit=limit,
        ):
            fact_id = str(fact["id"])
            version = int(fact["version"])
            path = fact_note_path(
                fact_id,
                layout=self.layout,
                space_slug=space_slug,
                profile_external_ref=profile_external_ref,
            )
            existing_conflict = self._existing_note_conflict(path)
            if existing_conflict is not None:
                changes.append(
                    ExportChange(
                        status=ExportStatus.CONFLICT,
                        path=path,
                        fact_id=fact_id,
                        message=existing_conflict,
                        version=version,
                    )
                )
                continue
            markdown = render_fact_note(
                fact,
                space_slug=space_slug,
                profile_external_ref=profile_external_ref,
            )
            self.vault.write_text(path, markdown)
            note = parse_fact_note(path, markdown)
            self.state.save(state_record_for_note(note))
            changes.append(
                ExportChange(
                    status=ExportStatus.EXPORTED,
                    path=path,
                    fact_id=fact_id,
                    version=version,
                )
            )
        return ExportFactsResult(changes=tuple(changes))

    def _existing_note_conflict(self, path: PurePosixPath) -> str | None:
        if not self.vault.exists(path):
            return None
        try:
            note = parse_fact_note(path, self.vault.read_text(path))
        except NoteFormatError as exc:
            return f"Existing managed note is not parseable: {exc}"
        if note.changed_since_export:
            return "Existing managed note has unimported local edits"
        return None


@dataclass
class PreviewVaultSyncUseCase:
    memory: MemoryGatewayPort
    vault: VaultPort
    state: SyncStateStorePort
    layout: ObsidianVaultLayout = field(default_factory=ObsidianVaultLayout)

    def execute(
        self,
        *,
        space_slug: str,
        profile_external_ref: str,
        include_inbox: bool = True,
        limit: int = 100,
    ) -> PreviewVaultSyncResult:
        export_plan = self._preview_export(
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
            limit=limit,
        )
        managed_import = ImportVaultChangesUseCase(
            memory=self.memory,
            vault=self.vault,
            state=self.state,
            layout=self.layout,
        ).execute(
            apply=False,
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
        )
        if include_inbox:
            inbox_import = ImportInboxSuggestionsUseCase(
                memory=self.memory,
                vault=self.vault,
                state=self.state,
                layout=self.layout,
            ).execute(
                space_slug=space_slug,
                profile_external_ref=profile_external_ref,
                apply=False,
            )
            import_plan = merge_import_results(managed_import, inbox_import)
        else:
            import_plan = managed_import
        return PreviewVaultSyncResult(export_plan=export_plan, import_plan=import_plan)

    def _preview_export(
        self,
        *,
        space_slug: str,
        profile_external_ref: str,
        limit: int,
    ) -> ExportFactsResult:
        changes: list[ExportChange] = []
        for fact in _iter_facts(
            self.memory,
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
            limit=limit,
        ):
            fact_id = str(fact["id"])
            version = int(fact["version"])
            path = fact_note_path(
                fact_id,
                layout=self.layout,
                space_slug=space_slug,
                profile_external_ref=profile_external_ref,
            )
            change = self._preview_fact_export(fact=fact, path=path, version=version)
            changes.append(change)
        return ExportFactsResult(changes=tuple(changes))

    def _preview_fact_export(
        self,
        *,
        fact: dict[str, object],
        path: PurePosixPath,
        version: int,
    ) -> ExportChange:
        fact_id = str(fact["id"])
        if not self.vault.exists(path):
            return ExportChange(
                status=ExportStatus.WOULD_EXPORT,
                path=path,
                fact_id=fact_id,
                message="Would create managed fact note",
                version=version,
            )
        try:
            note = parse_fact_note(path, self.vault.read_text(path))
        except NoteFormatError as exc:
            return ExportChange(
                status=ExportStatus.CONFLICT,
                path=path,
                fact_id=fact_id,
                message=f"Existing managed note is not parseable: {exc}",
                version=version,
            )
        if note.changed_since_export:
            return ExportChange(
                status=ExportStatus.CONFLICT,
                path=path,
                fact_id=fact_id,
                message="Existing managed note has unimported local edits",
                version=version,
            )
        expected_hash = content_hash(str(fact.get("text") or "").strip("\n"))
        if note.version == version and note.stored_hash == expected_hash:
            return ExportChange(
                status=ExportStatus.SKIPPED,
                path=path,
                fact_id=fact_id,
                message="Managed fact note is already current",
                version=version,
            )
        return ExportChange(
            status=ExportStatus.WOULD_EXPORT,
            path=path,
            fact_id=fact_id,
            message="Would refresh managed fact note",
            version=version,
        )


@dataclass
class ImportVaultChangesUseCase:
    memory: MemoryGatewayPort
    vault: VaultPort
    state: SyncStateStorePort
    layout: ObsidianVaultLayout = field(default_factory=ObsidianVaultLayout)
    _seen_fact_ids: set[str] = field(default_factory=set, init=False)

    def execute(
        self,
        *,
        apply: bool = False,
        space_slug: str = "default",
        profile_external_ref: str = "default",
    ) -> ImportVaultChangesResult:
        self._seen_fact_ids = set()
        changes: list[ImportChange] = []
        for directory in self.layout.fact_scan_dirs(
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
        ):
            changes.extend(
                self._import_path(path=path, apply=apply)
                for path in self.vault.iter_markdown_files(directory)
                if not _is_hidden_path(path)
            )
        return ImportVaultChangesResult(changes=tuple(changes))

    def _import_path(self, *, path: PurePosixPath, apply: bool) -> ImportChange:
        try:
            note = parse_fact_note(path, self.vault.read_text(path))
        except NoteFormatError as exc:
            return ImportChange(status=ImportStatus.CONFLICT, path=path, message=str(exc))

        if note.fact_id in self._seen_fact_ids:
            return ImportChange(
                status=ImportStatus.CONFLICT,
                path=path,
                fact_id=note.fact_id,
                message="Duplicate memo_stack_id in vault",
            )
        self._seen_fact_ids.add(note.fact_id)

        if note.sync_mode != SyncMode.DIRECT:
            return ImportChange(
                status=ImportStatus.SKIPPED,
                path=path,
                fact_id=note.fact_id,
                message=f"sync mode is {note.sync_mode.value}",
                version=note.version,
            )
        if not note.changed_since_export:
            backend_fact = self._backend_fact(note.fact_id)
            if str(backend_fact.get("status") or "") == "deleted":
                self.vault.delete_text(path)
                return ImportChange(
                    status=ImportStatus.REMOVED,
                    path=path,
                    fact_id=note.fact_id,
                    message="Removed clean local note for deleted backend fact",
                    version=note.version,
                )
            self.state.save(state_record_for_note(note))
            return ImportChange(
                status=ImportStatus.UNCHANGED,
                path=path,
                fact_id=note.fact_id,
                version=note.version,
            )

        backend_fact = self._backend_fact(note.fact_id)
        backend_version = int(backend_fact["version"])
        if backend_version != note.version:
            return ImportChange(
                status=ImportStatus.CONFLICT,
                path=path,
                fact_id=note.fact_id,
                message=(
                    f"Stale version: note has {note.version}, backend has {backend_version}"
                ),
                version=note.version,
            )

        if not apply:
            return ImportChange(
                status=ImportStatus.WOULD_UPDATE,
                path=path,
                fact_id=note.fact_id,
                message="Managed text differs from exported hash",
                version=note.version,
            )

        response = self.memory.update_fact(
            note.fact_id,
            expected_version=note.version,
            text=note.text,
            reason=f"Updated from Obsidian note {path.as_posix()}",
            source_refs=_source_refs_for_update(
                backend_fact=backend_fact,
                path=path,
                text=note.text,
            ),
        )
        updated_fact = response["data"]
        rendered = render_fact_note(
            updated_fact,
            space_slug=str(note.frontmatter.get("memo_stack_space_slug") or ""),
            profile_external_ref=str(
                note.frontmatter.get("memo_stack_profile_external_ref") or ""
            ),
        )
        self.vault.write_text(path, rendered)
        updated_note = parse_fact_note(path, rendered)
        self.state.save(state_record_for_note(updated_note))
        return ImportChange(
            status=ImportStatus.UPDATED,
            path=path,
            fact_id=note.fact_id,
            message=f"Updated to version {updated_fact['version']}",
            version=int(updated_fact["version"]),
        )

    def _backend_fact(self, fact_id: str) -> dict[str, object]:
        response = self.memory.get_fact(fact_id)
        return dict(response["data"])


def _source_refs_for_update(
    *,
    backend_fact: dict[str, object],
    path: PurePosixPath,
    text: str,
) -> list[dict[str, object]]:
    refs = [
        dict(ref)
        for ref in backend_fact.get("source_refs", [])
        if isinstance(ref, dict)
    ]
    obsidian_ref = {
        "source_type": "obsidian",
        "source_id": path.as_posix(),
        "quote_preview": text[:200],
    }
    for index, ref in enumerate(refs):
        if ref.get("source_type") == "obsidian" and ref.get("source_id") == path.as_posix():
            refs[index] = obsidian_ref
            break
    else:
        refs.append(obsidian_ref)
    return refs


@dataclass
class ImportInboxSuggestionsUseCase:
    memory: MemoryGatewayPort
    vault: VaultPort
    state: SyncStateStorePort
    layout: ObsidianVaultLayout = field(default_factory=ObsidianVaultLayout)

    def execute(
        self,
        *,
        space_slug: str,
        profile_external_ref: str,
        apply: bool = False,
    ) -> ImportVaultChangesResult:
        changes: list[ImportChange] = []
        for directory in self.layout.inbox_scan_dirs(
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
        ):
            changes.extend(
                self._import_path(
                    path=path,
                    space_slug=space_slug,
                    profile_external_ref=profile_external_ref,
                    apply=apply,
                )
                for path in self.vault.iter_markdown_files(directory)
                if not _is_helper_note(path)
            )
        return ImportVaultChangesResult(changes=tuple(changes))

    def _import_path(
        self,
        *,
        path: PurePosixPath,
        space_slug: str,
        profile_external_ref: str,
        apply: bool,
    ) -> ImportChange:
        try:
            text = _inbox_body(self.vault.read_text(path))
        except FrontmatterError as exc:
            return ImportChange(status=ImportStatus.CONFLICT, path=path, message=str(exc))
        if not text:
            return ImportChange(
                status=ImportStatus.SKIPPED,
                path=path,
                message="Inbox note is empty",
            )
        if len(text) > MAX_INBOX_SUGGESTION_CHARS:
            return ImportChange(
                status=ImportStatus.CONFLICT,
                path=path,
                message=(
                    "Inbox note is too large for one suggestion "
                    f"({len(text)} > {MAX_INBOX_SUGGESTION_CHARS})"
                ),
            )

        fingerprint = content_hash(f"{path.as_posix()}\n{text}")[:80]
        current_hash = content_hash(text)
        previous = self.state.get(path)
        if previous is not None and previous.content_hash == current_hash:
            return ImportChange(status=ImportStatus.UNCHANGED, path=path)
        if not apply:
            return ImportChange(
                status=ImportStatus.WOULD_SUGGEST,
                path=path,
                message="Inbox note would create a pending suggestion",
            )

        self.memory.create_suggestion(
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
            candidate_text=text,
            safe_reason=f"Imported from Obsidian inbox note {path.as_posix()}",
            source_refs=[
                {
                    "source_type": "obsidian",
                    "source_id": path.as_posix(),
                    "quote_preview": text[:200],
                }
            ],
            candidate_fingerprint=fingerprint,
        )
        self.state.save(
            SyncStateRecord(
                path=path,
                memo_stack_id=fingerprint,
                kind=NoteKind.INBOX,
                version=1,
                content_hash=current_hash,
            )
        )
        return ImportChange(
            status=ImportStatus.SUGGESTED,
            path=path,
            message="Created pending suggestion",
        )


@dataclass
class SyncVaultOnceUseCase:
    importer: ImportVaultChangesUseCase
    inbox_importer: ImportInboxSuggestionsUseCase
    exporter: ExportFactsToVaultUseCase

    def execute(
        self,
        *,
        space_slug: str,
        profile_external_ref: str,
        apply_import: bool = False,
        include_inbox: bool = True,
    ) -> SyncVaultOnceResult:
        managed_import = self.importer.execute(
            apply=apply_import,
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
        )
        if include_inbox:
            inbox_import = self.inbox_importer.execute(
                space_slug=space_slug,
                profile_external_ref=profile_external_ref,
                apply=apply_import,
            )
            import_result = merge_import_results(managed_import, inbox_import)
        else:
            import_result = managed_import

        export_skip_reason = _sync_export_skip_reason(
            import_result,
            apply_import=apply_import,
        )
        if export_skip_reason:
            return SyncVaultOnceResult(
                import_result=import_result,
                export_skipped_reason=export_skip_reason,
            )

        export_result = self.exporter.execute(
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
        )
        return SyncVaultOnceResult(
            import_result=import_result,
            export_result=export_result,
        )


def merge_import_results(*results: ImportVaultChangesResult) -> ImportVaultChangesResult:
    changes: list[ImportChange] = []
    for result in results:
        changes.extend(result.changes)
    return ImportVaultChangesResult(changes=tuple(changes))


def _sync_export_skip_reason(
    import_result: ImportVaultChangesResult,
    *,
    apply_import: bool,
) -> str:
    if import_result.conflicts:
        return "Import has conflicts; export skipped until conflicts are reviewed."
    if not apply_import and import_result.would_update:
        return (
            "Direct managed note edits are pending dry-run; rerun sync with "
            "--apply-import before exporting fresh backend projections."
        )
    return ""


def _inbox_body(markdown: str) -> str:
    _frontmatter, body = split_frontmatter(markdown)
    return body.strip()


def _is_hidden_path(path: PurePosixPath) -> bool:
    return any(part.startswith(".") for part in path.parts)


def _is_helper_note(path: PurePosixPath) -> bool:
    return _is_hidden_path(path) or path.name == "README.md"


def _iter_facts(
    memory: MemoryGatewayPort,
    *,
    space_slug: str,
    profile_external_ref: str,
    limit: int,
) -> tuple[dict[str, object], ...]:
    cursor: str | None = None
    facts: list[dict[str, object]] = []
    while True:
        response = memory.list_facts(
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
            limit=limit,
            cursor=cursor,
        )
        facts.extend(dict(fact) for fact in response.get("data", []))
        cursor = response.get("next_cursor")
        if not cursor:
            return tuple(facts)
