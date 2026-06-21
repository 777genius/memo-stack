"""Doctor checks for local Infinity Context."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from infinity_context_cli.config import DEFAULT_SERVICE_TOKEN, InfinityContextCliConfig
from infinity_context_cli.mcp_config import SUPPORTED_AGENTS
from infinity_context_cli.runtime import docker_available, docker_compose_available


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def run_doctor(config: InfinityContextCliConfig, *, timeout: float = 3.0) -> list[DoctorCheck]:
    checks = [
        DoctorCheck(
            name="repo_root",
            ok=(config.repo_dir / "docker-compose.yml").exists(),
            message=(
                "repo root resolved"
                if (config.repo_dir / "docker-compose.yml").exists()
                else "docker-compose.yml not found"
            ),
            details={"repo_dir": str(config.repo_dir)},
        ),
        DoctorCheck(
            name="docker",
            ok=docker_available(),
            message="docker command available" if docker_available() else "docker command missing",
        ),
        DoctorCheck(
            name="docker_compose",
            ok=docker_compose_available(),
            message=(
                "docker compose available"
                if docker_compose_available()
                else "docker compose unavailable"
            ),
        ),
        DoctorCheck(
            name="service_token",
            ok=bool(config.service_token),
            message=(
                "service token configured"
                if config.service_token and config.service_token != DEFAULT_SERVICE_TOKEN
                else "service token configured with default local token"
            ),
            details={"default_local_token": config.service_token == DEFAULT_SERVICE_TOKEN},
        ),
        _mcp_generated_config_check(config),
    ]
    checks.extend(_api_checks(config, timeout=timeout))
    return checks


def doctor_payload(config: InfinityContextCliConfig, checks: list[DoctorCheck]) -> dict[str, Any]:
    return {
        "ok": all(check.ok for check in checks),
        "api_url": config.api_url,
        "home": str(config.home),
        "repo_dir": str(config.repo_dir),
        "checks": [
            {
                "name": check.name,
                "ok": check.ok,
                "message": check.message,
                "details": check.details,
            }
            for check in checks
        ],
    }


def _api_checks(config: InfinityContextCliConfig, *, timeout: float) -> list[DoctorCheck]:
    headers = {"Authorization": f"Bearer {config.service_token}"}
    checks: list[DoctorCheck] = []
    try:
        with httpx.Client(base_url=config.api_url, timeout=timeout, headers=headers) as client:
            health = client.get("/v1/health")
            checks.append(
                DoctorCheck(
                    name="api_health",
                    ok=health.is_success,
                    message=(
                        "health endpoint reachable"
                        if health.is_success
                        else f"health returned HTTP {health.status_code}"
                    ),
                    details=_safe_json(health),
                )
            )
            capabilities = client.get("/v1/capabilities")
            checks.append(
                DoctorCheck(
                    name="api_capabilities",
                    ok=capabilities.is_success,
                    message=(
                        "capabilities endpoint reachable"
                        if capabilities.is_success
                        else f"capabilities returned HTTP {capabilities.status_code}"
                    ),
                    details=_safe_json(capabilities),
                )
            )
            ui = client.get("/ui/")
            title_present = "Infinity Context Browser" in ui.text
            checks.append(
                DoctorCheck(
                    name="ui_browser",
                    ok=ui.is_success and title_present,
                    message=(
                        "visual memory browser reachable"
                        if ui.is_success and title_present
                        else f"visual memory browser returned HTTP {ui.status_code}"
                    ),
                    details={
                        "status_code": ui.status_code,
                        "title_present": title_present,
                        "path": "/ui/",
                    },
                )
            )
    except httpx.HTTPError as exc:
        checks.append(
            DoctorCheck(
                name="api",
                ok=False,
                message="api unreachable",
                details={"error": exc.__class__.__name__},
            )
        )
    return checks


def _mcp_generated_config_check(config: InfinityContextCliConfig) -> DoctorCheck:
    generated_dir = config.home / "generated"
    entries = []
    for agent in sorted(SUPPORTED_AGENTS):
        path = generated_dir / f"{agent}-mcp.json"
        if path.exists():
            entries.append(_mcp_generated_config_entry(agent=agent, path=path))
    ready_agents = [entry["agent"] for entry in entries if entry["ready"]]
    existing_agents = [entry["agent"] for entry in entries]
    return DoctorCheck(
        name="mcp_generated_configs",
        ok=bool(ready_agents),
        message=(
            f"generated MCP config ready for {', '.join(ready_agents)}"
            if ready_agents
            else (
                "generated MCP config found but auth is not ready for "
                f"{', '.join(existing_agents)}"
            )
            if existing_agents
            else "no generated MCP config found"
        ),
        details={
            "generated_dir": str(generated_dir),
            "agents": existing_agents,
            "ready_agents": ready_agents,
            "missing_agents": [
                agent for agent in sorted(SUPPORTED_AGENTS) if agent not in existing_agents
            ],
            "configs": entries,
        },
    )


def _mcp_generated_config_entry(*, agent: str, path: Path) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "agent": agent,
        "path": str(path),
        "ready": False,
        "auth_source": "missing",
        "token_included": False,
        "token_file_exists": False,
    }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        entry["error"] = exc.__class__.__name__
        return entry
    server = _mcp_server_config(payload)
    env = server.get("env") if isinstance(server, dict) else {}
    env = env if isinstance(env, dict) else {}
    raw_token = str(env.get("MEMORY_MCP_AUTH_TOKEN") or "").strip()
    token_file = str(env.get("MEMORY_MCP_AUTH_TOKEN_FILE") or "").strip()
    entry["env_keys"] = sorted(str(key) for key in env)
    if raw_token and not raw_token.startswith("${"):
        entry["ready"] = True
        entry["auth_source"] = "inline_token"
        entry["token_included"] = True
    elif token_file:
        token_path = Path(token_file).expanduser()
        entry["auth_source"] = "token_file"
        entry["token_file"] = str(token_path)
        entry["token_file_exists"] = token_path.exists()
        entry["ready"] = token_path.exists()
    elif raw_token.startswith("${") and (
        os.environ.get("MEMORY_MCP_AUTH_TOKEN") or os.environ.get("MEMORY_SERVICE_TOKEN")
    ):
        entry["ready"] = True
        entry["auth_source"] = "process_env"
    elif raw_token.startswith("${"):
        entry["auth_source"] = "unresolved_env_placeholder"
    return entry


def _mcp_server_config(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("infinity-context"), dict):
        return payload["infinity-context"]
    servers = payload.get("mcpServers")
    if isinstance(servers, dict) and isinstance(servers.get("infinity-context"), dict):
        return servers["infinity-context"]
    return {}


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {"status_code": response.status_code}
    if isinstance(payload, dict):
        payload.pop("token", None)
        payload.pop("auth_token", None)
        return payload
    return {"status_code": response.status_code}
