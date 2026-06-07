"""Production load helpers for the full-provider smoke."""

from __future__ import annotations

import os
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx


def prod_load_settings(
    *,
    failure_cls: type[Exception] = RuntimeError,
) -> dict[str, int | float | bool]:
    return {
        "profiles": bounded_int_env(
            "MEMORY_CLEAN_SMOKE_LOAD_PROFILES",
            default=3,
            minimum=2,
            maximum=12,
            failure_cls=failure_cls,
        ),
        "facts_per_profile": bounded_int_env(
            "MEMORY_CLEAN_SMOKE_LOAD_FACTS_PER_PROFILE",
            default=8,
            minimum=3,
            maximum=100,
            failure_cls=failure_cls,
        ),
        "documents": bounded_int_env(
            "MEMORY_CLEAN_SMOKE_LOAD_DOCUMENTS",
            default=3,
            minimum=1,
            maximum=30,
            failure_cls=failure_cls,
        ),
        "large_doc_sections": bounded_int_env(
            "MEMORY_CLEAN_SMOKE_LOAD_LARGE_DOC_SECTIONS",
            default=18,
            minimum=3,
            maximum=80,
            failure_cls=failure_cls,
        ),
        "concurrency": bounded_int_env(
            "MEMORY_CLEAN_SMOKE_LOAD_CONCURRENCY",
            default=6,
            minimum=1,
            maximum=24,
            failure_cls=failure_cls,
        ),
        "chaos_requests": bounded_int_env(
            "MEMORY_CLEAN_SMOKE_LOAD_CHAOS_REQUESTS",
            default=16,
            minimum=1,
            maximum=200,
            failure_cls=failure_cls,
        ),
        "context_requests": bounded_int_env(
            "MEMORY_CLEAN_SMOKE_LOAD_CONTEXT_REQUESTS",
            default=10,
            minimum=1,
            maximum=200,
            failure_cls=failure_cls,
        ),
        "worker_rounds": bounded_int_env(
            "MEMORY_CLEAN_SMOKE_LOAD_WORKER_ROUNDS",
            default=40,
            minimum=1,
            maximum=300,
            failure_cls=failure_cls,
        ),
        "max_p95_ms": bounded_float_env(
            "MEMORY_CLEAN_SMOKE_LOAD_MAX_P95_MS",
            default=15_000.0,
            minimum=1_000.0,
            maximum=120_000.0,
            failure_cls=failure_cls,
        ),
        "restart_server": _bool(os.getenv("MEMORY_CLEAN_SMOKE_LOAD_RESTART_SERVER", "true")),
        "restart_providers": _bool(os.getenv("MEMORY_CLEAN_SMOKE_LOAD_RESTART_PROVIDERS", "true")),
        "provider_outage": _bool(os.getenv("MEMORY_CLEAN_SMOKE_LOAD_PROVIDER_OUTAGE", "true")),
    }


def bounded_int_env(
    name: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
    failure_cls: type[Exception] = RuntimeError,
) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise failure_cls(f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise failure_cls(f"{name} must be between {minimum} and {maximum}")
    return value


def bounded_float_env(
    name: str,
    *,
    default: float,
    minimum: float,
    maximum: float,
    failure_cls: type[Exception] = RuntimeError,
) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise failure_cls(f"{name} must be numeric") from exc
    if value < minimum or value > maximum:
        raise failure_cls(f"{name} must be between {minimum:g} and {maximum:g}")
    return value


def parallel_post_json(
    *,
    base_url: str,
    token: str,
    requests: list[dict[str, Any]],
    concurrency: int,
) -> list[dict[str, Any]]:
    def run_one(request: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {token}"}
        idempotency_key = request.get("idempotency_key")
        if isinstance(idempotency_key, str) and idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        with httpx.Client(base_url=base_url, headers=headers, timeout=90) as client:
            response = client.post(str(request["path"]), json=request["json"])
        try:
            payload: Any = response.json()
        except ValueError:
            payload = {"text": response.text}
        return {
            "label": request.get("label"),
            "status": response.status_code,
            "data": payload.get("data") if isinstance(payload, Mapping) else None,
            "error": payload.get("error") if isinstance(payload, Mapping) else None,
        }

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(run_one, request) for request in requests]
        return [future.result() for future in as_completed(futures)]


def single_result_data(
    results: list[dict[str, Any]],
    label: str,
    *,
    failure_cls: type[Exception] = RuntimeError,
) -> dict[str, Any]:
    matches = [
        item["data"]
        for item in results
        if item.get("label") == label
        and item.get("status") in {200, 201}
        and isinstance(item.get("data"), Mapping)
    ]
    if len(matches) != 1:
        raise failure_cls(f"Expected one successful result for {label}, got {len(matches)}")
    return dict(matches[0])


def successful_result_ids(results: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for item in results:
        data = item.get("data")
        if item.get("status") in {200, 201} and isinstance(data, Mapping):
            item_id = data.get("id")
            if isinstance(item_id, str):
                ids.add(item_id)
    return ids


def large_prod_document_text(*, marker: str, tail_sentinel: str, sections: int) -> str:
    paragraphs = [
        (
            f"{marker}: PROD_LARGE_DOC_SECTION_{index:02d} contains production runbook "
            "notes about memory worker recovery, provider lag, projection freshness, "
            "source citations, scoped retrieval, prompt-injection resistance, and "
            "coding-agent memory continuity after restarts. "
            "This paragraph is intentionally verbose so the document produces several "
            "chunks and exercises Qdrant recall beyond a tiny happy-path note."
        )
        for index in range(sections)
    ]
    paragraphs.append(tail_sentinel)
    return "\n\n".join(paragraphs)


def run_prod_chaos_flood(
    *,
    base_url: str,
    token: str,
    marker: str,
    requests: int,
) -> dict[str, int]:
    server_error_count = 0
    unauthorized_count = 0
    validation_count = 0
    not_found_count = 0
    with (
        httpx.Client(
            base_url=base_url,
            headers={"Authorization": "Bearer prod-load-wrong-token"},
            timeout=10,
        ) as wrong_client,
        httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        ) as client,
    ):
        for index in range(requests):
            unauthorized = wrong_client.post(
                "/v1/facts",
                json={
                    "space_slug": "prod-load-chaos",
                    "profile_external_ref": "wrong-token",
                    "text": f"{marker}: unauthorized chaos request {index}",
                    "kind": "note",
                    "source_refs": [{"source_type": "prod_load", "source_id": f"unauth:{index}"}],
                },
            )
            invalid = client.post(
                "/v1/context",
                json={
                    "space_slug": "prod-load-chaos",
                    "profile_external_ref": "invalid-context",
                    "query": "",
                },
            )
            missing = client.patch(
                f"/v1/facts/missing-{marker}-{index}",
                json={
                    "expected_version": 1,
                    "text": f"{marker}: missing update",
                    "reason": "prod load chaos missing fact",
                    "source_refs": [{"source_type": "prod_load", "source_id": f"missing:{index}"}],
                },
            )
            for response in (unauthorized, invalid, missing):
                if response.status_code >= 500:
                    server_error_count += 1
            if unauthorized.status_code == 401:
                unauthorized_count += 1
            if invalid.status_code == 400:
                validation_count += 1
            if missing.status_code == 404:
                not_found_count += 1
    return {
        "requests": requests * 3,
        "unauthorized_count": unauthorized_count,
        "validation_count": validation_count,
        "not_found_count": not_found_count,
        "server_error_count": server_error_count,
    }


def active_outbox_counts(counts: Mapping[str, Any]) -> dict[str, int]:
    return {
        str(key): int(value)
        for key, value in counts.items()
        if key != "done" and isinstance(value, int) and value > 0
    }


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile_value)))
    return float(ordered[index])


def _bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}
