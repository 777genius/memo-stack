"""MCP-facing Obsidian setup and sync helpers."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx
from infinity_context_obsidian.conflicts import WriteConflictArtifactsUseCase
from infinity_context_obsidian.doctor import DoctorVaultUseCase
from infinity_context_obsidian.gateway import SdkMemoryGateway
from infinity_context_obsidian.layout import ObsidianVaultLayout
from infinity_context_obsidian.plugin_install import InstallObsidianPluginUseCase
from infinity_context_obsidian.setup import SetupVaultUseCase
from infinity_context_obsidian.state import SqliteSyncStateStore
from infinity_context_obsidian.sync import (
    ExportFactsToVaultUseCase,
    ImportInboxSuggestionsUseCase,
    ImportVaultChangesResult,
    ImportVaultChangesUseCase,
    PreviewVaultSyncResult,
    PreviewVaultSyncUseCase,
    SyncVaultOnceResult,
    SyncVaultOnceUseCase,
)
from infinity_context_obsidian.vault import FilesystemVault
from infinity_context_sdk import InfinityContextClient, InfinityContextError

from infinity_context_mcp.config import MemoryMcpSettings
from infinity_context_mcp.domain.models import (
    McpDiagnostics,
    McpToolError,
    MemoryGatewayError,
    public_error_code,
    safe_message,
)


class ObsidianMcpService:
    def __init__(self, *, settings: MemoryMcpSettings) -> None:
        self._settings = settings

    async def status(
        self,
        *,
        vault_path: str | None = None,
        obsidian_config_dir: str | None = None,
        root_folder: str | None = None,
        layout_version: str | None = None,
        space_slug: str | None = None,
        memory_scope_external_ref: str | None = None,
        require_plugin: bool = False,
    ) -> dict[str, Any]:
        async def action() -> dict[str, Any]:
            request = self._request(
                vault_path=vault_path,
                obsidian_config_dir=obsidian_config_dir,
                root_folder=root_folder,
                layout_version=layout_version,
                space_slug=space_slug,
                memory_scope_external_ref=memory_scope_external_ref,
            )
            if not self._settings.obsidian_enabled:
                return self._ok(
                    "Obsidian MCP tools are disabled by local policy.",
                    data={
                        **request,
                        "enabled": False,
                        "sync_enabled": self._settings.obsidian_sync_enabled,
                        "configured": False,
                        "status": "disabled",
                    },
                    warnings=["Set MEMORY_MCP_OBSIDIAN_ENABLED=true to enable vault setup."],
                )
            if request["vault_path"] is None:
                return self._ok(
                    "Obsidian MCP tools are enabled but no vault path is configured.",
                    data={
                        **request,
                        "enabled": True,
                        "sync_enabled": self._settings.obsidian_sync_enabled,
                        "configured": False,
                        "status": "missing_vault",
                    },
                    degraded=True,
                )
            doctor = DoctorVaultUseCase(vault_path=Path(str(request["vault_path"]))).execute(
                api_url=self._settings.api_url,
                token=self._settings.auth_token,
                space_slug=str(request["space_slug"]),
                memory_scope_external_ref=str(request["memory_scope_external_ref"]),
                root_folder=str(request["root_folder"]),
                layout_version=str(request["layout_version"]),
                obsidian_config_dir=str(request["obsidian_config_dir"]),
                require_plugin=require_plugin,
                check_health=True,
            )
            return self._ok(
                "Obsidian vault status computed.",
                data={
                    **request,
                    "enabled": True,
                    "sync_enabled": self._settings.obsidian_sync_enabled,
                    "configured": doctor.ok,
                    "status": "ready" if doctor.ok else "needs_attention",
                    "checks": [asdict(check) for check in doctor.checks],
                },
                degraded=not doctor.ok,
            )

        return await self._guard(action)

    async def setup(
        self,
        *,
        vault_path: str | None = None,
        obsidian_config_dir: str | None = None,
        root_folder: str | None = None,
        layout_version: str | None = None,
        space_slug: str | None = None,
        memory_scope_external_ref: str | None = None,
        apply: bool = False,
        overwrite: bool = False,
        install_plugin: bool = False,
        enable_plugin: bool = False,
    ) -> dict[str, Any]:
        async def action() -> dict[str, Any]:
            self._ensure_obsidian_enabled()
            request = self._request(
                vault_path=vault_path,
                obsidian_config_dir=obsidian_config_dir,
                root_folder=root_folder,
                layout_version=layout_version,
                space_slug=space_slug,
                memory_scope_external_ref=memory_scope_external_ref,
            )
            vault = self._require_vault_path(request)
            context = self._context(request)
            setup = context["setup"]
            result = (
                setup.execute(
                    space_slug=str(request["space_slug"]),
                    memory_scope_external_ref=str(request["memory_scope_external_ref"]),
                    overwrite=overwrite,
                )
                if apply
                else setup.plan(
                    space_slug=str(request["space_slug"]),
                    memory_scope_external_ref=str(request["memory_scope_external_ref"]),
                    overwrite=overwrite,
                )
            )
            plugin_result = None
            if install_plugin and apply:
                plugin_result = InstallObsidianPluginUseCase(
                    vault_path=vault,
                    obsidian_config_dir=str(request["obsidian_config_dir"]),
                ).execute(
                    overwrite=overwrite,
                    enable=enable_plugin,
                    settings=self._plugin_settings(request),
                )
            data = {
                **request,
                "enabled": True,
                "sync_enabled": self._settings.obsidian_sync_enabled,
                "configured": True,
                "status": "setup_applied" if apply else "setup_planned",
                "dry_run": not apply,
                "applied": apply,
                "written": list(result.written) if apply else [],
                "would_write": [] if apply else list(result.written),
                "skipped": list(result.skipped),
                "would_install_plugin": bool(install_plugin and not apply),
                "plugin_installed": bool(plugin_result),
                "plugin_enabled": bool(plugin_result.enabled) if plugin_result else None,
                "settings_path": str(plugin_result.settings_path) if plugin_result else None,
            }
            side_effects = ["obsidian_setup_files_written"] if apply else []
            if plugin_result:
                side_effects.append("obsidian_plugin_installed")
            return self._ok(
                "Obsidian vault setup applied." if apply else "Obsidian vault setup planned.",
                data=data,
                side_effects=side_effects,
            )

        return await self._guard(action)

    async def preview(
        self,
        *,
        vault_path: str | None = None,
        obsidian_config_dir: str | None = None,
        root_folder: str | None = None,
        layout_version: str | None = None,
        space_slug: str | None = None,
        memory_scope_external_ref: str | None = None,
        include_inbox: bool = True,
    ) -> dict[str, Any]:
        async def action() -> dict[str, Any]:
            self._ensure_obsidian_enabled()
            request = self._request(
                vault_path=vault_path,
                obsidian_config_dir=obsidian_config_dir,
                root_folder=root_folder,
                layout_version=layout_version,
                space_slug=space_slug,
                memory_scope_external_ref=memory_scope_external_ref,
            )
            self._require_vault_path(request)
            result = self._context(request)["previewer"].execute(
                space_slug=str(request["space_slug"]),
                memory_scope_external_ref=str(request["memory_scope_external_ref"]),
                include_inbox=include_inbox,
            )
            return self._ok(
                "Obsidian sync preview completed.",
                data={
                    **request,
                    "enabled": True,
                    "sync_enabled": self._settings.obsidian_sync_enabled,
                    "configured": True,
                    "status": "preview_ok" if result.ok else "preview_conflicts",
                    "dry_run": True,
                    **_preview_data(result),
                },
                degraded=not result.ok,
            )

        return await self._guard(action)

    async def sync(
        self,
        *,
        vault_path: str | None = None,
        obsidian_config_dir: str | None = None,
        root_folder: str | None = None,
        layout_version: str | None = None,
        space_slug: str | None = None,
        memory_scope_external_ref: str | None = None,
        apply: bool = False,
        apply_import: bool = False,
        include_inbox: bool = True,
    ) -> dict[str, Any]:
        async def action() -> dict[str, Any]:
            self._ensure_obsidian_enabled()
            if not apply:
                preview = await self.preview(
                    vault_path=vault_path,
                    obsidian_config_dir=obsidian_config_dir,
                    root_folder=root_folder,
                    layout_version=layout_version,
                    space_slug=space_slug,
                    memory_scope_external_ref=memory_scope_external_ref,
                    include_inbox=include_inbox,
                )
                preview["message"] = "Obsidian sync dry-run completed."
                return preview
            self._ensure_sync_enabled()
            request = self._request(
                vault_path=vault_path,
                obsidian_config_dir=obsidian_config_dir,
                root_folder=root_folder,
                layout_version=layout_version,
                space_slug=space_slug,
                memory_scope_external_ref=memory_scope_external_ref,
            )
            self._require_vault_path(request)
            context = self._context(request)
            result = context["syncer"].execute(
                space_slug=str(request["space_slug"]),
                memory_scope_external_ref=str(request["memory_scope_external_ref"]),
                apply_import=apply_import,
                include_inbox=include_inbox,
            )
            import_conflicts = context["conflict_writer"].execute(
                direction="import",
                changes=result.import_result.changes,
                space_slug=str(request["space_slug"]),
                memory_scope_external_ref=str(request["memory_scope_external_ref"]),
            )
            export_conflicts = context["conflict_writer"].execute(
                direction="export",
                changes=result.export_result.changes,
                space_slug=str(request["space_slug"]),
                memory_scope_external_ref=str(request["memory_scope_external_ref"]),
            )
            return self._ok(
                "Obsidian sync completed." if result.ok else "Obsidian sync needs review.",
                data={
                    **request,
                    "enabled": True,
                    "sync_enabled": self._settings.obsidian_sync_enabled,
                    "configured": True,
                    "status": "sync_ok" if result.ok else "sync_needs_review",
                    "dry_run": False,
                    "applied": True,
                    **_sync_data(
                        result,
                        import_conflict_artifacts=import_conflicts.paths,
                        export_conflict_artifacts=export_conflicts.paths,
                    ),
                },
                side_effects=["obsidian_sync"],
                degraded=not result.ok,
            )

        return await self._guard(action)

    def _request(
        self,
        *,
        vault_path: str | None,
        obsidian_config_dir: str | None,
        root_folder: str | None,
        layout_version: str | None,
        space_slug: str | None,
        memory_scope_external_ref: str | None,
    ) -> dict[str, Any]:
        return {
            "vault_path": vault_path or self._settings.obsidian_vault_path,
            "obsidian_config_dir": (
                obsidian_config_dir or self._settings.obsidian_config_dir
            ),
            "root_folder": root_folder or self._settings.obsidian_root_folder,
            "layout_version": layout_version or self._settings.obsidian_layout_version,
            "space_slug": space_slug or self._settings.default_space_slug,
            "memory_scope_external_ref": (
                memory_scope_external_ref or self._settings.default_memory_scope_external_ref
            ),
        }

    def _context(self, request: dict[str, Any]) -> dict[str, Any]:
        vault_path = self._require_vault_path(request)
        vault = FilesystemVault(vault_path)
        layout = ObsidianVaultLayout.from_values(
            root_folder=str(request["root_folder"]),
            version=str(request["layout_version"]),
        )
        state = SqliteSyncStateStore(vault_path / ".infinity-context" / "obsidian-sync.sqlite3")
        gateway = SdkMemoryGateway(
            InfinityContextClient(
                base_url=self._settings.api_url,
                token=self._settings.auth_token,
            )
        )
        exporter = ExportFactsToVaultUseCase(
            memory=gateway,
            vault=vault,
            state=state,
            layout=layout,
        )
        importer = ImportVaultChangesUseCase(
            memory=gateway,
            vault=vault,
            state=state,
            layout=layout,
        )
        inbox_importer = ImportInboxSuggestionsUseCase(
            memory=gateway,
            vault=vault,
            state=state,
            layout=layout,
        )
        return {
            "setup": SetupVaultUseCase(vault=vault, layout=layout),
            "previewer": PreviewVaultSyncUseCase(
                memory=gateway,
                vault=vault,
                state=state,
                layout=layout,
            ),
            "syncer": SyncVaultOnceUseCase(
                importer=importer,
                inbox_importer=inbox_importer,
                exporter=exporter,
            ),
            "conflict_writer": WriteConflictArtifactsUseCase(vault=vault, layout=layout),
        }

    def _plugin_settings(self, request: dict[str, Any]) -> dict[str, Any]:
        vault_path = Path(str(request["vault_path"])).expanduser().resolve()
        return {
            "apiUrl": self._settings.api_url,
            "token": "",
            "localCliPath": "infinity-context",
            "cliPath": "infinity-context-obsidian",
            "vaultPathOverride": str(vault_path),
            "spaceSlug": str(request["space_slug"]),
            "memoryScopeExternalRef": str(request["memory_scope_external_ref"]),
            "rootFolder": str(request["root_folder"]),
            "layoutVersion": str(request["layout_version"]),
            "applyImportOnSync": False,
            "commandTimeoutMs": int(self._settings.request_timeout_seconds * 1000),
        }

    def _require_vault_path(self, request: dict[str, Any]) -> Path:
        vault_path = request.get("vault_path")
        if not vault_path:
            raise MemoryGatewayError(
                status_code=400,
                code="infinity_context_mcp.obsidian.missing_vault",
                message="Obsidian vault path is required",
                retryable=False,
            )
        return Path(str(vault_path)).expanduser().resolve()

    def _ensure_obsidian_enabled(self) -> None:
        if not self._settings.obsidian_enabled:
            raise MemoryGatewayError(
                status_code=403,
                code="infinity_context_mcp.obsidian.disabled",
                message="Obsidian MCP tools are disabled by local policy",
                retryable=False,
            )

    def _ensure_sync_enabled(self) -> None:
        if not self._settings.obsidian_sync_enabled:
            raise MemoryGatewayError(
                status_code=403,
                code="infinity_context_mcp.obsidian.sync_disabled",
                message="Mutating Obsidian sync is disabled by local policy",
                retryable=False,
            )

    async def _guard(self, action) -> dict[str, Any]:
        try:
            return await action()
        except (InfinityContextError, httpx.HTTPError, OSError, ValueError) as exc:
            return self._error(
                code="infinity_context_mcp.obsidian.error",
                message=str(exc),
                status_code=500,
                retryable=True,
            )
        except MemoryGatewayError as exc:
            return self._error(
                code=exc.code,
                message=exc.message,
                status_code=exc.status_code,
                retryable=exc.retryable,
            )

    def _ok(
        self,
        message: str,
        *,
        data: dict[str, Any],
        side_effects: list[str] | None = None,
        warnings: list[str] | None = None,
        degraded: bool = False,
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "message": message,
            "data": data,
            "diagnostics": McpDiagnostics(
                trace_id=uuid.uuid4().hex,
                side_effects=side_effects or [],
                warnings=warnings or [],
                degraded=degraded,
            ).model_dump(exclude_none=True),
        }

    def _error(
        self,
        *,
        code: str,
        message: str,
        status_code: int | None,
        retryable: bool,
    ) -> dict[str, Any]:
        public_code = (
            code
            if code.startswith("infinity_context_mcp.obsidian.")
            else public_error_code(code, status_code=status_code)
        )
        safe = safe_message(message)
        return {
            "ok": False,
            "message": safe,
            "error": McpToolError(
                status_code=status_code,
                code=public_code,
                message=safe,
                safe_message=safe,
                retryable=retryable,
            ).model_dump(exclude_none=True),
            "diagnostics": McpDiagnostics(
                trace_id=uuid.uuid4().hex,
                backend={"code": safe_message(code), "status_code": status_code},
                degraded=True,
            ).model_dump(exclude_none=True),
        }


def _preview_data(result: PreviewVaultSyncResult) -> dict[str, Any]:
    return {
        "import_result": {
            "would_update": result.import_plan.would_update,
            "would_suggest": result.import_plan.would_suggest,
            "conflicts": result.import_plan.conflicts,
            "changes": _import_changes(result.import_plan),
        },
        "export_result": {
            "exported": result.export_plan.would_export,
            "skipped": result.export_plan.skipped,
            "conflicts": result.export_plan.conflicts,
            "paths": list(result.export_plan.paths),
            "changes": _export_changes(result.export_plan.changes),
        },
    }


def _sync_data(
    result: SyncVaultOnceResult,
    *,
    import_conflict_artifacts: tuple[str, ...],
    export_conflict_artifacts: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "export_skipped": result.export_skipped,
        "export_skipped_reason": result.export_skipped_reason,
        "import_result": {
            "updated": result.import_result.updated,
            "would_update": result.import_result.would_update,
            "suggested": result.import_result.suggested,
            "would_suggest": result.import_result.would_suggest,
            "conflicts": result.import_result.conflicts,
            "conflict_artifacts_written": len(import_conflict_artifacts),
            "conflict_artifacts": list(import_conflict_artifacts),
            "changes": _import_changes(result.import_result),
        },
        "export_result": {
            "exported": result.export_result.exported,
            "skipped": result.export_result.skipped,
            "conflicts": result.export_result.conflicts,
            "conflict_artifacts_written": len(export_conflict_artifacts),
            "paths": list(result.export_result.paths),
            "conflict_artifacts": list(export_conflict_artifacts),
            "changes": _export_changes(result.export_result.changes),
        },
    }


def _import_changes(result: ImportVaultChangesResult) -> list[dict[str, Any]]:
    return [
        {
            **asdict(change),
            "status": change.status.value,
            "path": change.path.as_posix(),
        }
        for change in result.changes
    ]


def _export_changes(changes: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [
        {
            **asdict(change),
            "status": change.status.value,
            "path": change.path.as_posix(),
        }
        for change in changes
    ]
