"""Doctor checks for local Infinity Context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from infinity_context_cli.config import DEFAULT_SERVICE_TOKEN, InfinityContextCliConfig
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
