"""MCP-facing helpers for local Infinity Context runtime setup."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx
from infinity_context_cli.config import (
    DEFAULT_API_URL,
    DEFAULT_HOME,
    DEFAULT_SERVICE_TOKEN,
    init_local_config,
    load_config,
)
from infinity_context_cli.doctor import run_doctor
from infinity_context_cli.runtime import DockerComposeRuntime, RuntimeResult
from infinity_context_core.application.sensitive_text import redact_sensitive_text

from infinity_context_mcp.config import MemoryMcpSettings
from infinity_context_mcp.domain.models import (
    McpDiagnostics,
    McpToolError,
    MemoryGatewayError,
    public_error_code,
    safe_message,
)

_OUTPUT_LIMIT = 4000


class LocalRuntimeMcpService:
    def __init__(self, *, settings: MemoryMcpSettings) -> None:
        self._settings = settings

    async def status(self, *, home: str | None = None) -> dict[str, Any]:
        async def action() -> dict[str, Any]:
            request = self._request(home=home, repo_dir=None, api_url=None)
            if not self._settings.local_runtime_enabled:
                return self._ok(
                    "Local runtime MCP tools are disabled by local policy.",
                    data={
                        **request,
                        "enabled": False,
                        "start_enabled": self._settings.local_runtime_start_enabled,
                        "status": "disabled",
                    },
                    warnings=[
                        "Set MEMORY_MCP_LOCAL_RUNTIME_ENABLED=true to enable local runtime setup."
                    ],
                )

            config = load_config(Path(str(request["home"])))
            checks = self._status_checks(config)
            api_checks = [check for check in checks if check["name"].startswith("api_")]
            api_ok = bool(api_checks) and all(bool(check["ok"]) for check in api_checks)
            config_exists = config.config_path.exists()
            status = "ready" if api_ok else "configured" if config_exists else "uninitialized"
            return self._ok(
                "Local runtime status computed.",
                data={
                    **self._config_data(config),
                    "enabled": True,
                    "start_enabled": self._settings.local_runtime_start_enabled,
                    "status": status,
                    "checks": checks,
                },
                degraded=status != "ready",
            )

        return await self._guard(action)

    async def init(
        self,
        *,
        home: str | None = None,
        repo_dir: str | None = None,
        api_url: str | None = None,
        apply: bool = False,
        force: bool = False,
    ) -> dict[str, Any]:
        async def action() -> dict[str, Any]:
            self._ensure_enabled()
            request = self._request(home=home, repo_dir=repo_dir, api_url=api_url)
            home_path = Path(str(request["home"])).expanduser()
            repo_path = self._repo_path(request)
            resolved_api_url = str(request["api_url"] or DEFAULT_API_URL).rstrip("/")
            if not apply:
                would_write = self._init_would_write(home_path, force=force)
                return self._ok(
                    "Local runtime init planned.",
                    data={
                        **request,
                        "enabled": True,
                        "start_enabled": self._settings.local_runtime_start_enabled,
                        "status": "init_planned",
                        "dry_run": True,
                        "applied": False,
                        "repo_dir": str(repo_path),
                        "api_url": resolved_api_url,
                        "config_path": str(home_path / "config.toml"),
                        "env_path": str(home_path / ".env"),
                        "would_write": would_write,
                    },
                )

            before = self._known_init_paths(home_path)
            config = init_local_config(
                home=home_path,
                repo_dir=repo_path,
                api_url=resolved_api_url,
                force=force,
            )
            written = [
                str(path)
                for path, existed in before.items()
                if path.exists() and (force or not existed)
            ]
            return self._ok(
                "Local runtime init applied.",
                data={
                    **self._config_data(config),
                    "enabled": True,
                    "start_enabled": self._settings.local_runtime_start_enabled,
                    "status": "init_applied",
                    "dry_run": False,
                    "applied": True,
                    "written": written,
                },
                side_effects=["local_runtime_config_written"],
            )

        return await self._guard(action)

    async def doctor(self, *, home: str | None = None) -> dict[str, Any]:
        async def action() -> dict[str, Any]:
            self._ensure_enabled()
            request = self._request(home=home, repo_dir=None, api_url=None)
            config = load_config(Path(str(request["home"])))
            checks = [_doctor_check(asdict(check)) for check in run_doctor(config)]
            ok = all(bool(check["ok"]) for check in checks)
            return self._ok(
                "Local runtime doctor completed.",
                data={
                    **self._config_data(config),
                    "enabled": True,
                    "start_enabled": self._settings.local_runtime_start_enabled,
                    "status": "ready" if ok else "needs_attention",
                    "checks": checks,
                },
                degraded=not ok,
            )

        return await self._guard(action)

    async def start(
        self,
        *,
        compose_profile: str = "lite",
        home: str | None = None,
        apply: bool = False,
    ) -> dict[str, Any]:
        async def action() -> dict[str, Any]:
            self._ensure_enabled()
            request = self._request(home=home, repo_dir=None, api_url=None)
            command = list(_planned_start_command(compose_profile))
            if not apply:
                return self._ok(
                    "Local runtime start planned.",
                    data={
                        **request,
                        "enabled": True,
                        "start_enabled": self._settings.local_runtime_start_enabled,
                        "status": "start_planned",
                        "dry_run": True,
                        "applied": False,
                        "start_compose_profile": compose_profile,
                        "command": command,
                    },
                )
            self._ensure_start_enabled()
            config = load_config(Path(str(request["home"])))
            result = DockerComposeRuntime(config=config).up(compose_profile)
            return self._ok(
                "Local runtime start completed."
                if result.ok
                else "Local runtime start failed.",
                data={
                    **self._config_data(config),
                    "enabled": True,
                    "start_enabled": self._settings.local_runtime_start_enabled,
                    "status": "started" if result.ok else "start_failed",
                    "dry_run": False,
                    "applied": True,
                    "start_compose_profile": compose_profile,
                    "runtime_result": _runtime_result(result, token=config.service_token),
                },
                side_effects=["local_runtime_started"] if result.ok else [],
                degraded=not result.ok,
            )

        return await self._guard(action)

    def _request(
        self,
        *,
        home: str | None,
        repo_dir: str | None,
        api_url: str | None,
    ) -> dict[str, Any]:
        return {
            "home": str(
                Path(home or self._settings.local_runtime_home or DEFAULT_HOME).expanduser()
            ),
            "repo_dir": (
                str(Path(repo_dir or self._settings.local_runtime_repo_dir).expanduser())
                if repo_dir or self._settings.local_runtime_repo_dir
                else None
            ),
            "api_url": (api_url or self._settings.api_url or DEFAULT_API_URL).rstrip("/"),
        }

    def _repo_path(self, request: dict[str, Any]) -> Path:
        repo_dir = request.get("repo_dir")
        if repo_dir:
            return Path(str(repo_dir)).expanduser()
        return load_config(Path(str(request["home"]))).repo_dir

    def _status_checks(self, config) -> list[dict[str, Any]]:
        checks = [
            {
                "name": "config",
                "ok": config.config_path.exists(),
                "message": "config file exists"
                if config.config_path.exists()
                else "config file missing",
                "details": _details({"path": str(config.config_path)}),
            },
            {
                "name": "env",
                "ok": config.env_path.exists(),
                "message": "env file exists" if config.env_path.exists() else "env file missing",
                "details": _details({"path": str(config.env_path)}),
            },
            {
                "name": "repo_root",
                "ok": (config.repo_dir / "docker-compose.yml").exists(),
                "message": "repo root resolved"
                if (config.repo_dir / "docker-compose.yml").exists()
                else "docker-compose.yml not found",
                "details": _details({"repo_dir": str(config.repo_dir)}),
            },
        ]
        checks.extend(_api_status_checks(config))
        return checks

    def _config_data(self, config) -> dict[str, Any]:
        return {
            "home": str(config.home),
            "repo_dir": str(config.repo_dir),
            "api_url": config.api_url,
            "config_path": str(config.config_path),
            "env_path": str(config.env_path),
            "config_exists": config.config_path.exists(),
            "env_exists": config.env_path.exists(),
            "token_configured": bool(config.service_token),
            "default_local_token": config.service_token == DEFAULT_SERVICE_TOKEN,
            "runtime_compose_profile": config.runtime_compose_profile,
            "compose_project_name": config.compose_project_name,
        }

    def _init_would_write(self, home: Path, *, force: bool) -> list[str]:
        return [
            str(path)
            for path, existed in self._known_init_paths(home).items()
            if force or not existed
        ]

    def _known_init_paths(self, home: Path) -> dict[Path, bool]:
        paths = [
            home,
            home / "logs",
            home / "run",
            home / "config.toml",
            home / ".env",
        ]
        return {path: path.exists() for path in paths}

    def _ensure_enabled(self) -> None:
        if not self._settings.local_runtime_enabled:
            raise MemoryGatewayError(
                status_code=403,
                code="infinity_context_mcp.local_runtime.disabled",
                message="Local runtime MCP tools are disabled by local policy",
                retryable=False,
            )

    def _ensure_start_enabled(self) -> None:
        if not self._settings.local_runtime_start_enabled:
            raise MemoryGatewayError(
                status_code=403,
                code="infinity_context_mcp.local_runtime.start_disabled",
                message="Starting the local runtime is disabled by local policy",
                retryable=False,
            )

    async def _guard(self, action) -> dict[str, Any]:
        try:
            return await action()
        except (httpx.HTTPError, OSError, ValueError) as exc:
            return self._error(
                code="infinity_context_mcp.local_runtime.error",
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
            if code.startswith("infinity_context_mcp.local_runtime.")
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


def _api_status_checks(config) -> list[dict[str, Any]]:
    headers = {"Authorization": f"Bearer {config.service_token}"}
    try:
        with httpx.Client(base_url=config.api_url, timeout=3.0, headers=headers) as client:
            health = client.get("/v1/health")
            capabilities = client.get("/v1/capabilities")
    except httpx.HTTPError as exc:
        return [
            {
                "name": "api",
                "ok": False,
                "message": "api unreachable",
                "details": _details({"error": exc.__class__.__name__}),
            }
        ]
    return [
        {
            "name": "api_health",
            "ok": health.is_success,
            "message": "health endpoint reachable"
            if health.is_success
            else f"health returned HTTP {health.status_code}",
            "details": _details({"status_code": health.status_code}),
        },
        {
            "name": "api_capabilities",
            "ok": capabilities.is_success,
            "message": "capabilities endpoint reachable"
            if capabilities.is_success
            else f"capabilities returned HTTP {capabilities.status_code}",
            "details": _details({"status_code": capabilities.status_code}),
        },
    ]


def _doctor_check(check: dict[str, Any]) -> dict[str, Any]:
    details = check.get("details", {})
    return {
        "name": check.get("name"),
        "ok": check.get("ok"),
        "message": check.get("message"),
        "details": _details(details if isinstance(details, dict) else {}),
    }


def _details(values: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"key": str(key), "value": _scalar(value)} for key, value in values.items()]


def _scalar(value: Any) -> str | int | bool | None:
    if value is None or isinstance(value, bool | int | str):
        return value
    return str(value)[:500]


def _planned_start_command(compose_profile: str) -> tuple[str, ...]:
    if compose_profile == "full":
        return (
            "docker",
            "compose",
            "--profile",
            "full",
            "up",
            "-d",
            "infinity_context_server_full",
            "infinity_context_worker_full",
            "infinity_context_extraction_worker_full",
        )
    return (
        "docker",
        "compose",
        "--profile",
        "lite",
        "up",
        "-d",
        "infinity_context_server",
        "infinity_context_worker",
        "infinity_context_extraction_worker",
    )


def _runtime_result(result: RuntimeResult, *, token: str) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "command": list(result.command),
        "returncode": result.returncode,
        "stdout": _safe_output(result.stdout, token),
        "stderr": _safe_output(result.stderr, token),
    }


def _safe_output(value: str, token: str) -> str:
    redacted = value.replace(token, "[redacted]") if token else value
    return redact_sensitive_text(redacted)[:_OUTPUT_LIMIT]
