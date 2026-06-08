"""High-level MCP setup flows for Memo Stack integrations."""

from __future__ import annotations

import uuid
from typing import Any

from memo_stack_mcp.application.local_runtime import LocalRuntimeMcpService
from memo_stack_mcp.application.obsidian import ObsidianMcpService
from memo_stack_mcp.domain.models import McpDiagnostics, McpToolError, safe_message


class ObsidianPrepareMcpService:
    def __init__(
        self,
        *,
        local_runtime: LocalRuntimeMcpService,
        obsidian: ObsidianMcpService,
    ) -> None:
        self._local_runtime = local_runtime
        self._obsidian = obsidian

    async def prepare(
        self,
        *,
        vault_path: str | None = None,
        obsidian_config_dir: str | None = None,
        root_folder: str | None = None,
        layout_version: str | None = None,
        space_slug: str | None = None,
        profile_external_ref: str | None = None,
        home: str | None = None,
        repo_dir: str | None = None,
        api_url: str | None = None,
        apply: bool = False,
        force: bool = False,
        overwrite: bool = False,
        install_plugin: bool = True,
        enable_plugin: bool = True,
        include_inbox: bool = True,
    ) -> dict[str, Any]:
        local_init = await self._local_runtime.init(
            home=home,
            repo_dir=repo_dir,
            api_url=api_url,
            apply=apply,
            force=force,
        )
        if not _ok(local_init):
            return self._failed(
                "Local runtime init failed.",
                status="local_runtime_init_failed",
                local_runtime=_data(local_init),
                source=local_init,
            )

        obsidian_setup = await self._obsidian.setup(
            vault_path=vault_path,
            obsidian_config_dir=obsidian_config_dir,
            root_folder=root_folder,
            layout_version=layout_version,
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
            apply=apply,
            overwrite=overwrite,
            install_plugin=install_plugin,
            enable_plugin=enable_plugin,
        )
        if not _ok(obsidian_setup):
            return self._failed(
                "Obsidian vault setup failed.",
                status="obsidian_setup_failed",
                local_runtime=_data(local_init),
                obsidian_setup=_data(obsidian_setup),
                source=obsidian_setup,
                side_effects=_side_effects(local_init),
            )

        if not apply:
            return self._ok(
                "Memo Stack Obsidian prepare planned.",
                data={
                    "status": "prepare_planned",
                    "dry_run": True,
                    "applied": False,
                    "local_runtime": _data(local_init),
                    "obsidian_setup": _data(obsidian_setup),
                    "next_actions": [
                        "Review planned local config and vault/plugin writes.",
                        "Call memory_obsidian_prepare with apply=true after user approval.",
                    ],
                },
            )

        local_status = await self._local_runtime.status(home=home)
        side_effects = _side_effects(local_init) + _side_effects(obsidian_setup)
        if not _api_ready(local_status):
            return self._ok(
                "Memo Stack Obsidian prepared. Backend is not ready yet.",
                data={
                    "status": "prepared_backend_not_ready",
                    "dry_run": False,
                    "applied": True,
                    "local_runtime": _data(local_init),
                    "obsidian_setup": _data(obsidian_setup),
                    "local_status": _data(local_status),
                    "next_actions": [
                        "Start local Memo Stack runtime explicitly when ready.",
                        "Run memory_obsidian_preview after backend status is ready.",
                    ],
                },
                side_effects=side_effects,
                degraded=True,
            )

        preview = await self._obsidian.preview(
            vault_path=vault_path,
            obsidian_config_dir=obsidian_config_dir,
            root_folder=root_folder,
            layout_version=layout_version,
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
            include_inbox=include_inbox,
        )
        if not _ok(preview):
            return self._failed(
                "Obsidian preview failed after setup.",
                status="obsidian_preview_failed",
                local_runtime=_data(local_init),
                obsidian_setup=_data(obsidian_setup),
                local_status=_data(local_status),
                obsidian_preview=_data(preview),
                source=preview,
                side_effects=side_effects,
            )

        return self._ok(
            "Memo Stack Obsidian prepared and preview checked.",
            data={
                "status": "prepared_preview_ok",
                "dry_run": False,
                "applied": True,
                "local_runtime": _data(local_init),
                "obsidian_setup": _data(obsidian_setup),
                "local_status": _data(local_status),
                "obsidian_preview": _data(preview),
                "next_actions": [
                    "Review preview results.",
                    "Run memory_obsidian_sync only after explicit user approval.",
                ],
            },
            side_effects=side_effects,
            degraded=_degraded(preview),
        )

    def _ok(
        self,
        message: str,
        *,
        data: dict[str, Any],
        side_effects: list[str] | None = None,
        degraded: bool = False,
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "message": message,
            "data": data,
            "diagnostics": McpDiagnostics(
                trace_id=uuid.uuid4().hex,
                side_effects=side_effects or [],
                degraded=degraded,
            ).model_dump(exclude_none=True),
        }

    def _failed(
        self,
        message: str,
        *,
        status: str,
        source: dict[str, Any],
        side_effects: list[str] | None = None,
        **data: Any,
    ) -> dict[str, Any]:
        error = _error(source)
        public_message = safe_message(error.get("message") or message)
        return {
            "ok": False,
            "message": public_message,
            "data": {
                "status": status,
                "dry_run": False,
                "applied": bool(side_effects),
                **data,
            },
            "error": McpToolError(
                status_code=error.get("status_code"),
                code=str(error.get("code") or "memo_stack_mcp.prepare.error"),
                message=public_message,
                safe_message=public_message,
                retryable=bool(error.get("retryable")),
            ).model_dump(exclude_none=True),
            "diagnostics": McpDiagnostics(
                trace_id=uuid.uuid4().hex,
                side_effects=side_effects or [],
                backend={
                    "code": safe_message(str(error.get("code") or "")),
                    "status_code": error.get("status_code"),
                },
                degraded=True,
            ).model_dump(exclude_none=True),
        }


def _ok(payload: dict[str, Any]) -> bool:
    return payload.get("ok") is True


def _data(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = payload.get("data")
    return data if isinstance(data, dict) else None


def _error(payload: dict[str, Any]) -> dict[str, Any]:
    error = payload.get("error")
    return error if isinstance(error, dict) else {}


def _diagnostics(payload: dict[str, Any]) -> dict[str, Any]:
    diagnostics = payload.get("diagnostics")
    return diagnostics if isinstance(diagnostics, dict) else {}


def _side_effects(payload: dict[str, Any]) -> list[str]:
    side_effects = _diagnostics(payload).get("side_effects")
    return [str(item) for item in side_effects] if isinstance(side_effects, list) else []


def _degraded(payload: dict[str, Any]) -> bool:
    return bool(_diagnostics(payload).get("degraded"))


def _api_ready(payload: dict[str, Any]) -> bool:
    data = _data(payload) or {}
    if data.get("status") == "ready":
        return True
    checks = data.get("checks")
    if not isinstance(checks, list):
        return False
    api_checks = [
        check
        for check in checks
        if isinstance(check, dict) and str(check.get("name", "")).startswith("api_")
    ]
    return bool(api_checks) and all(check.get("ok") is True for check in api_checks)
