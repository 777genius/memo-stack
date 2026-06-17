#!/usr/bin/env python3
"""Live smoke for MemoryScope snapshot thread transfer."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SmokeFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class SmokeConfig:
    api_url: str
    auth_token: str
    space_prefix: str = "snapshot-thread-smoke"
    source_memory_scope: str = "source-memory-scope"
    restore_base_memory_scope: str = "restore-base"
    thread_external_ref: str = "snapshot-thread"
    timeout: float = 30.0
    report_out: Path | None = None


RequestJson = Callable[
    [str, str, SmokeConfig, dict[str, Any] | None, dict[str, str] | None],
    dict[str, Any],
]


def main() -> int:
    config = _parse_args()
    report = run_smoke(config)
    if config.report_out is not None:
        config.report_out.parent.mkdir(parents=True, exist_ok=True)
        config.report_out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


def run_smoke(
    config: SmokeConfig,
    *,
    request_json: RequestJson = lambda method, path, cfg, body, params: _request_json(
        method,
        path,
        cfg,
        body,
        params,
    ),
    time_ns: Callable[[], int] = time.time_ns,
) -> dict[str, Any]:
    _wait_for_health(config, request_json=request_json)
    run_id = str(time_ns())
    space_slug = f"{config.space_prefix}-{run_id}"

    capture = request_json(
        "POST",
        "/v1/captures",
        config,
        {
            "space_slug": space_slug,
            "memory_scope_external_ref": config.source_memory_scope,
            "thread_external_ref": config.thread_external_ref,
            "source_agent": "snapshot-thread-smoke",
            "source_kind": "manual",
            "event_type": "SnapshotThreadSmoke",
            "actor_role": "user",
            "text": f"SNAPSHOT_THREAD_SMOKE_{run_id}: save this into the source thread.",
            "source_authority": "user_statement",
            "idempotency_key": f"snapshot-thread-smoke-{run_id}",
            "consolidate": False,
        },
        None,
    )["data"]

    suggestions = request_json(
        "POST",
        "/v1/link-suggestions",
        config,
        {
            "space_slug": space_slug,
            "memory_scope_external_ref": config.source_memory_scope,
            "thread_external_ref": config.thread_external_ref,
            "source_type": "capture",
            "source_id": capture["id"],
            "text": "snapshot thread memory",
            "limit": 10,
            "persist": True,
        },
        None,
    )["data"]["candidates"]
    thread_candidate = _find_thread_candidate(suggestions)
    source_thread_id = str(thread_candidate["target_id"])
    if not thread_candidate.get("suggestion_id"):
        raise SmokeFailure("Thread candidate was not persisted")

    exported = request_json(
        "GET",
        "/v1/export/memory_scope-snapshot",
        config,
        None,
        {
            "space_slug": space_slug,
            "memory_scope_external_ref": config.source_memory_scope,
            "redacted": "false",
        },
    )
    snapshot = exported["data"]
    manifest = exported["manifest"]
    _assert_snapshot_thread_payload(
        snapshot=snapshot,
        counts=exported["counts"],
        source_thread_id=source_thread_id,
    )

    imported = request_json(
        "POST",
        "/v1/export/memory_scope-snapshot/import",
        config,
        {
            "space_slug": space_slug,
            "memory_scope_external_ref": config.restore_base_memory_scope,
            "snapshot": snapshot,
            "manifest": manifest,
            "dry_run": False,
            "merge_strategy": "create_new_memory_scope",
            "confirmed": True,
            "source_name": f"snapshot-thread-smoke-{run_id}",
        },
        None,
    )["data"]
    if imported.get("status") != "ok":
        raise SmokeFailure(f"Snapshot import failed: {imported!r}")
    imported_counts = imported.get("imported") or {}
    if imported_counts.get("threads") != 1:
        raise SmokeFailure(f"Expected one imported thread, got {imported_counts!r}")
    if imported_counts.get("context_link_suggestions", 0) < 1:
        raise SmokeFailure(f"Expected imported context link suggestion, got {imported_counts!r}")

    restored_scope = imported["created_memory_scope"]["external_ref"]
    browser = request_json(
        "GET",
        "/v1/memory-browser",
        config,
        None,
        {
            "space_slug": space_slug,
            "memory_scope_external_ref": str(restored_scope),
            "suggestion_status": "pending",
        },
    )["data"]
    restored_thread = _single_restored_thread(browser, config.thread_external_ref)
    restored_thread_id = str(restored_thread["id"])
    if restored_thread_id == source_thread_id:
        raise SmokeFailure("Restored thread id was not remapped")
    restored_suggestion = _find_restored_thread_suggestion(browser, restored_thread_id)

    reviewed = request_json(
        "POST",
        f"/v1/context-link-suggestions/{restored_suggestion['id']}/review",
        config,
        {"action": "approve", "reason": "snapshot thread smoke"},
        None,
    )["data"]
    if reviewed["suggestion"]["status"] != "approved":
        raise SmokeFailure(f"Restored suggestion was not approved: {reviewed!r}")
    link = reviewed["link"]
    if link["target_type"] != "thread" or str(link["target_id"]) != restored_thread_id:
        raise SmokeFailure(f"Approved link target is wrong: {link!r}")

    return {
        "status": "ok",
        "api_url": config.api_url,
        "space_slug": space_slug,
        "source_memory_scope": config.source_memory_scope,
        "restored_memory_scope": restored_scope,
        "source_thread_id": source_thread_id,
        "restored_thread_id": restored_thread_id,
        "approved_suggestion_id": restored_suggestion["id"],
    }


def _parse_args() -> SmokeConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-url",
        default=os.getenv("MEMORY_SMOKE_API_URL", "http://127.0.0.1:7788"),
    )
    parser.add_argument(
        "--auth-token",
        default=os.getenv("MEMORY_SMOKE_AUTH_TOKEN")
        or os.getenv("MEMORY_SERVICE_TOKEN")
        or "local-dev-token",
    )
    parser.add_argument("--space-prefix", default="snapshot-thread-smoke")
    parser.add_argument("--source-memory-scope", default="source-memory-scope")
    parser.add_argument("--restore-base-memory-scope", default="restore-base")
    parser.add_argument("--thread-external-ref", default="snapshot-thread")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--report-out", type=Path)
    args = parser.parse_args()
    return SmokeConfig(
        api_url=args.api_url.rstrip("/"),
        auth_token=args.auth_token,
        space_prefix=args.space_prefix,
        source_memory_scope=args.source_memory_scope,
        restore_base_memory_scope=args.restore_base_memory_scope,
        thread_external_ref=args.thread_external_ref,
        timeout=args.timeout,
        report_out=args.report_out,
    )


def _wait_for_health(config: SmokeConfig, *, request_json: RequestJson) -> None:
    deadline = time.monotonic() + config.timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            response = request_json("GET", "/v1/health", config, None, None)
            if response.get("status") == "ok":
                return
        except Exception as exc:  # noqa: BLE001 - smoke diagnostics should stay compact.
            last_error = str(exc)
        time.sleep(1)
    raise SmokeFailure(f"Health check did not pass within {config.timeout}s: {last_error}")


def _request_json(
    method: str,
    path: str,
    config: SmokeConfig,
    body: dict[str, Any] | None,
    params: dict[str, str] | None,
) -> dict[str, Any]:
    url = config.api_url + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    payload = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers={
            "Authorization": f"Bearer {config.auth_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        raise SmokeFailure(f"{method} {path} failed {exc.code}: {raw}") from exc


def _find_thread_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    for candidate in candidates:
        if candidate.get("target_type") == "thread":
            return candidate
    raise SmokeFailure(f"No thread candidate in suggestions: {candidates!r}")


def _assert_snapshot_thread_payload(
    *,
    snapshot: dict[str, Any],
    counts: dict[str, Any],
    source_thread_id: str,
) -> None:
    if snapshot.get("schema_version") != 9:
        raise SmokeFailure(f"Expected snapshot schema v9, got {snapshot.get('schema_version')!r}")
    if counts.get("threads") != 1:
        raise SmokeFailure(f"Expected one exported thread, got {counts!r}")
    thread_ids = {str(thread.get("id")) for thread in snapshot.get("threads") or []}
    if source_thread_id not in thread_ids:
        raise SmokeFailure(f"Source thread missing from snapshot: {snapshot.get('threads')!r}")
    suggestions = snapshot.get("context_link_suggestions") or []
    if not any(
        suggestion.get("target_type") == "thread"
        and str(suggestion.get("target_id")) == source_thread_id
        for suggestion in suggestions
    ):
        raise SmokeFailure("Snapshot did not contain a persisted thread suggestion")


def _single_restored_thread(
    browser: dict[str, Any],
    expected_external_ref: str,
) -> dict[str, Any]:
    threads = [
        thread
        for thread in browser.get("threads") or []
        if thread.get("external_ref") == expected_external_ref
    ]
    if len(threads) != 1:
        raise SmokeFailure(f"Expected one restored thread, got {threads!r}")
    return threads[0]


def _find_restored_thread_suggestion(
    browser: dict[str, Any],
    restored_thread_id: str,
) -> dict[str, Any]:
    for suggestion in browser.get("context_link_suggestions") or []:
        if suggestion.get("target_type") != "thread":
            continue
        if str(suggestion.get("target_id")) != restored_thread_id:
            raise SmokeFailure(
                "Restored thread suggestion target did not remap: "
                f"{suggestion.get('target_id')!r} != {restored_thread_id!r}"
            )
        return suggestion
    raise SmokeFailure("No restored pending thread suggestion found")


if __name__ == "__main__":
    raise SystemExit(main())
