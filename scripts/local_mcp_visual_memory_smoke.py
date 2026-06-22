"""Run a local MCP plus visual memory smoke against a running server.

The smoke is intentionally sandboxed: it creates a unique memory_scope, saves a
single capture, waits for consolidation and verifies that visual review state is
visible through the memory browser API/UI. Provider keys are never required.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
from infinity_context_cli.config import init_local_config, load_config
from infinity_context_cli.mcp_config import render_mcp_config, write_mcp_config
from infinity_context_core.reporting import with_report_provenance

try:
    from scripts.clean_full_smoke_redaction import has_unredacted_secret_marker, redact_payload
except ModuleNotFoundError:
    from clean_full_smoke_redaction import has_unredacted_secret_marker, redact_payload


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUITE = "infinity-context-local-mcp-visual-memory-smoke"
DEFAULT_REPORT_OUT = ".e2e-artifacts/local-mcp-visual-memory-smoke.json"
DEFAULT_TIMEOUT_SECONDS = 30.0
NO_DEFAULT_THREAD_SENTINEL = "__INFINITY_CONTEXT_NO_DEFAULT_THREAD__"


class LocalVisualSmokeFailure(RuntimeError):
    """Raised when the local MCP visual memory path is not usable."""


def main() -> int:
    args = _parse_args()
    started = time.perf_counter()
    config = load_config()
    api_url = (args.api_url or os.getenv("MEMORY_API_URL") or config.api_url).rstrip("/")
    token = _resolve_token(config)
    run_id = str(time.time_ns())
    scope_ref = args.memory_scope or f"local-visual-{run_id[-10:]}"
    space_slug = args.space_slug
    checks: dict[str, Any] = {}
    failures: list[str] = []

    try:
        if not token:
            raise LocalVisualSmokeFailure("Missing MEMORY_MCP_AUTH_TOKEN or local service token")
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(base_url=api_url, headers=headers, timeout=10.0) as client:
            checks.update(_check_http_surfaces(client))
            checks["generated_mcp"] = _check_generated_mcp_config(
                api_url=api_url,
                token=token,
                write_config=not args.no_write_mcp_config,
            )
            if args.skip_mcp_session:
                checks["mcp_session"] = {"ok": True, "status": "skipped"}
            else:
                checks["mcp_session"] = asyncio.run(
                    _run_mcp_status(api_url=api_url, token=token, space_slug=space_slug)
                )
            marker = f"LOCAL_VISUAL_MCP_SMOKE_{run_id[-8:]}"
            capture = _create_capture(
                client,
                space_slug=space_slug,
                scope_ref=scope_ref,
                marker=marker,
            )
            checks["capture_created"] = {
                "ok": bool(capture.get("id")),
                "capture_id": capture.get("id"),
                "created_suggestions": capture.get("created_suggestions"),
            }
            checks["visual_memory"] = _wait_for_visual_memory(
                client,
                space_slug=space_slug,
                scope_ref=scope_ref,
                capture_id=str(capture.get("id") or ""),
                timeout_seconds=args.timeout_seconds,
            )
            if args.skip_mcp_session:
                checks["mcp_digest"] = {"ok": True, "status": "skipped"}
            else:
                checks["mcp_digest"] = asyncio.run(
                    _run_mcp_digest(
                        api_url=api_url,
                        token=token,
                        space_slug=space_slug,
                        scope_ref=scope_ref,
                        topic=marker,
                    )
                )
            suggestion_ids = (
                checks["visual_memory"].get("created_from_capture_suggestion_ids")
                if isinstance(checks.get("visual_memory"), dict)
                else []
            )
            suggestion_id = str(suggestion_ids[0]) if suggestion_ids else ""
            if args.skip_mcp_session:
                checks["mcp_reviewed_search"] = {"ok": True, "status": "skipped"}
            else:
                checks["mcp_reviewed_search"] = asyncio.run(
                    _run_mcp_reviewed_search(
                        api_url=api_url,
                        token=token,
                        space_slug=space_slug,
                        scope_ref=scope_ref,
                        topic=marker,
                        suggestion_id=suggestion_id,
                    )
                )
    except Exception as exc:
        failures.append(f"{exc.__class__.__name__}: {exc}")

    failures.extend(_failed_required_checks(checks))
    report = _build_report(
        api_url=api_url,
        space_slug=space_slug,
        scope_ref=scope_ref,
        checks=checks,
        failures=failures,
        started=started,
        run_id=run_id,
    )
    _emit_report(report, report_out=args.report_out, env=_secret_env(token))
    return 0 if report["ok"] else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=None)
    parser.add_argument("--space-slug", default="local-visual-smoke")
    parser.add_argument("--memory_scope", dest="memory_scope", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--report-out", default=DEFAULT_REPORT_OUT)
    parser.add_argument("--no-write-mcp-config", action="store_true")
    parser.add_argument("--skip-mcp-session", action="store_true")
    return parser.parse_args()


def _resolve_token(config: Any) -> str:
    return str(
        os.getenv("MEMORY_MCP_AUTH_TOKEN")
        or os.getenv("MEMORY_SERVICE_TOKEN")
        or config.service_token
        or ""
    )


def _check_http_surfaces(client: httpx.Client) -> dict[str, Any]:
    health = client.get("/v1/health")
    capabilities = client.get("/v1/capabilities")
    ui = client.get("/ui/")
    browser_js = client.get("/ui/assets/memory-browser.js")
    return {
        "health": {"ok": health.is_success, "status_code": health.status_code},
        "capabilities": {
            "ok": capabilities.is_success,
            "status_code": capabilities.status_code,
            "capture_mode": _json_at(capabilities, "captures", "mode"),
            "review_supported": _json_at(
                capabilities,
                "suggestions",
                "review_tool_supported",
            ),
        },
        "ui": {
            "ok": ui.is_success
            and "Infinity Context Browser" in ui.text
            and "first-memory-rail" in ui.text
            and "first-memory-guidance" in ui.text,
            "status_code": ui.status_code,
            "title_present": "Infinity Context Browser" in ui.text,
            "first_memory_rail": "first-memory-rail" in ui.text,
            "first_memory_guidance": "first-memory-guidance" in ui.text,
            "first_memory_next_step": "firstMemoryNextStep" in ui.text,
            "first_memory_evidence_kinds": "firstMemoryEvidenceKinds" in ui.text,
            "first_memory_review_state": "firstMemoryReviewState" in ui.text,
            "capture_deep_link": "/ui/#capture",
            "review_deep_link": "/ui/#review",
        },
        "ui_assets": {
            "ok": browser_js.is_success
            and "renderFirstMemoryRail" in browser_js.text
            and "firstMemoryEvidenceLabels" in browser_js.text
            and "activeExtractionModalities" in browser_js.text
            and "tabNameFromHash" in browser_js.text,
            "status_code": browser_js.status_code,
        },
    }


def _check_generated_mcp_config(*, api_url: str, token: str, write_config: bool) -> dict[str, Any]:
    config = load_config()
    init_local_config(home=config.home, repo_dir=config.repo_dir, api_url=api_url)
    config = replace(config, api_url=api_url, service_token=token)
    rendered = render_mcp_config(agent="codex", config=config, include_token=False)
    parsed = json.loads(rendered)
    server = parsed.get("infinity-context") or {}
    env = server.get("env") if isinstance(server, dict) else {}
    env = env if isinstance(env, dict) else {}
    path = (
        write_mcp_config(agent="codex", config=config, include_token=False)
        if write_config
        else None
    )
    command = str(server.get("command") or "")
    return {
        "ok": bool(command)
        and env.get("MEMORY_MCP_API_URL") == config.api_url
        and env.get("MEMORY_MCP_AUTH_TOKEN_FILE") == str(config.env_path)
        and env.get("MEMORY_MCP_DEFAULT_THREAD_EXTERNAL_REF") == NO_DEFAULT_THREAD_SENTINEL
        and token not in rendered
        and (path is None or path.exists()),
        "agent": "codex",
        "path": str(path) if path else None,
        "token_included": False,
        "token_file": str(config.env_path),
        "api_url": env.get("MEMORY_MCP_API_URL"),
        "no_default_thread": env.get("MEMORY_MCP_DEFAULT_THREAD_EXTERNAL_REF")
        == NO_DEFAULT_THREAD_SENTINEL,
        "raw_token_absent": token not in rendered,
        "write_config": write_config,
    }


async def _run_mcp_status(*, api_url: str, token: str, space_slug: str) -> dict[str, Any]:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ModuleNotFoundError as exc:
        return {"ok": False, "status": "blocked", "reason": f"missing dependency: {exc.name}"}

    env = os.environ.copy()
    env.update(
        {
            "MEMORY_MCP_API_URL": api_url,
            "MEMORY_MCP_AUTH_TOKEN": token,
            "MEMORY_MCP_DEFAULT_SPACE_SLUG": space_slug,
            "MEMORY_MCP_DEFAULT_MEMORY_SCOPE_EXTERNAL_REF": "local-visual-mcp-status",
            "MEMORY_MCP_DEFAULT_THREAD_EXTERNAL_REF": NO_DEFAULT_THREAD_SENTINEL,
            "MEMORY_MCP_AGENT_NAME": "local-visual-smoke",
            "MEMORY_MCP_TRANSPORT": "stdio",
        }
    )
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "infinity_context_mcp"],
        env=env,
    )
    try:
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            tool_names = {tool.name for tool in tools}
            result = await session.call_tool("memory_status", {})
            payload = (
                result.structuredContent
                if result.structuredContent is not None
                else json.loads(result.content[0].text)
            )
    except Exception as exc:
        return {"ok": False, "status": "failed", "reason": f"{exc.__class__.__name__}: {exc}"}
    return {
        "ok": bool(payload.get("ok")) and "memory_status" in tool_names,
        "status": "ok",
        "tool_count": len(tool_names),
        "memory_status_ok": bool(payload.get("ok")),
    }


async def _run_mcp_digest(
    *,
    api_url: str,
    token: str,
    space_slug: str,
    scope_ref: str,
    topic: str,
) -> dict[str, Any]:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ModuleNotFoundError as exc:
        return {"ok": False, "status": "blocked", "reason": f"missing dependency: {exc.name}"}

    env = os.environ.copy()
    env.update(
        {
            "MEMORY_MCP_API_URL": api_url,
            "MEMORY_MCP_AUTH_TOKEN": token,
            "MEMORY_MCP_DEFAULT_SPACE_SLUG": space_slug,
            "MEMORY_MCP_DEFAULT_MEMORY_SCOPE_EXTERNAL_REF": scope_ref,
            "MEMORY_MCP_DEFAULT_THREAD_EXTERNAL_REF": NO_DEFAULT_THREAD_SENTINEL,
            "MEMORY_MCP_AGENT_NAME": "local-visual-smoke",
            "MEMORY_MCP_TRANSPORT": "stdio",
        }
    )
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "infinity_context_mcp"],
        env=env,
    )
    try:
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            tool_names = {tool.name for tool in tools}
            result = await session.call_tool(
                "memory_digest",
                {
                    "topic": topic,
                    "space_slug": space_slug,
                    "memory_scope_external_ref": scope_ref,
                    "max_facts": 5,
                    "max_chunks": 0,
                    "max_suggestions": 5,
                    "include_pending_suggestions": True,
                    "include_related": False,
                },
            )
            payload = _tool_payload(result)
    except Exception as exc:
        return {"ok": False, "status": "failed", "reason": f"{exc.__class__.__name__}: {exc}"}

    digest = _summarize_mcp_digest_payload(payload=payload, topic=topic, token=token)
    return {
        **digest,
        "status": "ok" if digest["ok"] else "failed",
        "tool_present": "memory_digest" in tool_names,
    }


def _tool_payload(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    content = getattr(result, "content", None)
    if not content:
        return {}
    text = getattr(content[0], "text", None)
    if not isinstance(text, str):
        return {}
    try:
        payload = json.loads(text)
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _summarize_mcp_digest_payload(
    *,
    payload: dict[str, Any],
    topic: str,
    token: str,
) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    diagnostics = (
        data.get("diagnostics") if isinstance(data.get("diagnostics"), dict) else {}
    )
    sections = data.get("sections") if isinstance(data.get("sections"), list) else []
    markdown = str(data.get("rendered_markdown") or "")
    pending_section = next(
        (
            section
            for section in sections
            if isinstance(section, dict) and section.get("title") == "Pending suggestions"
        ),
        {},
    )
    pending_items = (
        pending_section.get("items")
        if isinstance(pending_section, dict) and isinstance(pending_section.get("items"), list)
        else []
    )
    pending_item_matches = any(
        isinstance(item, dict) and topic in str(item.get("text") or "")
        for item in pending_items
    )
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    checks = {
        "payload_ok": payload.get("ok") is True,
        "evidence_only": diagnostics.get("evidence_only") is True,
        "topic_visible": topic in markdown or data.get("topic") == topic,
        "pending_suggestion_visible": pending_item_matches,
        "pending_suggestions_considered": int(
            diagnostics.get("pending_suggestions_considered") or 0
        )
        >= 1,
        "not_canonical_marked": "not_canonical" in markdown,
        "raw_token_absent": token not in serialized,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "digest_id": data.get("digest_id"),
        "section_count": len(sections),
        "pending_suggestion_items": len(pending_items),
        "rendered_markdown_chars": len(markdown),
    }


async def _run_mcp_reviewed_search(
    *,
    api_url: str,
    token: str,
    space_slug: str,
    scope_ref: str,
    topic: str,
    suggestion_id: str,
) -> dict[str, Any]:
    if not suggestion_id:
        return {
            "ok": False,
            "status": "failed",
            "reason": "created_from_capture_suggestion_missing",
        }
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ModuleNotFoundError as exc:
        return {"ok": False, "status": "blocked", "reason": f"missing dependency: {exc.name}"}

    env = os.environ.copy()
    env.update(
        {
            "MEMORY_MCP_API_URL": api_url,
            "MEMORY_MCP_AUTH_TOKEN": token,
            "MEMORY_MCP_DEFAULT_SPACE_SLUG": space_slug,
            "MEMORY_MCP_DEFAULT_MEMORY_SCOPE_EXTERNAL_REF": scope_ref,
            "MEMORY_MCP_DEFAULT_THREAD_EXTERNAL_REF": NO_DEFAULT_THREAD_SENTINEL,
            "MEMORY_MCP_AGENT_NAME": "local-visual-smoke",
            "MEMORY_MCP_TRANSPORT": "stdio",
        }
    )
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "infinity_context_mcp"],
        env=env,
    )
    try:
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            tool_names = {tool.name for tool in tools}
            approve_result = await session.call_tool(
                "memory_approve_suggestion",
                {
                    "suggestion_id": suggestion_id,
                    "reason": "local visual smoke approved capture suggestion",
                },
            )
            approve_payload = _tool_payload(approve_result)
            search_result = await session.call_tool(
                "memory_search",
                {
                    "query": topic,
                    "space_slug": space_slug,
                    "memory_scope_external_ref": scope_ref,
                    "max_facts": 5,
                    "max_chunks": 0,
                    "token_budget": 2000,
                },
            )
            search_payload = _tool_payload(search_result)
    except Exception as exc:
        return {"ok": False, "status": "failed", "reason": f"{exc.__class__.__name__}: {exc}"}

    summary = _summarize_mcp_reviewed_search_payload(
        approve_payload=approve_payload,
        search_payload=search_payload,
        topic=topic,
        token=token,
    )
    return {
        **summary,
        "status": "ok" if summary["ok"] else "failed",
        "review_tool_present": "memory_approve_suggestion" in tool_names,
        "search_tool_present": "memory_search" in tool_names,
    }


def _summarize_mcp_reviewed_search_payload(
    *,
    approve_payload: dict[str, Any],
    search_payload: dict[str, Any],
    topic: str,
    token: str,
) -> dict[str, Any]:
    approve_data = (
        approve_payload.get("data") if isinstance(approve_payload.get("data"), dict) else {}
    )
    fact = approve_data.get("fact") if isinstance(approve_data.get("fact"), dict) else {}
    fact_id = fact.get("id")
    search_data = (
        search_payload.get("data") if isinstance(search_payload.get("data"), dict) else {}
    )
    items = search_data.get("items") if isinstance(search_data.get("items"), list) else []
    diagnostics = (
        search_data.get("diagnostics")
        if isinstance(search_data.get("diagnostics"), dict)
        else {}
    )
    quality = (
        diagnostics.get("retrieval_quality_summary")
        if isinstance(diagnostics.get("retrieval_quality_summary"), dict)
        else {}
    )
    rendered = str(search_data.get("rendered_text") or "")
    matching_items = [
        item
        for item in items
        if isinstance(item, dict) and topic in str(item.get("text") or "")
    ]
    item_citation_count = sum(
        len(item.get("citations") or [])
        for item in items
        if isinstance(item, dict) and isinstance(item.get("citations"), list)
    )
    item_source_ref_count = sum(
        len(item.get("source_refs") or [])
        for item in items
        if isinstance(item, dict) and isinstance(item.get("source_refs"), list)
    )
    rendered_citation_present = " citations=" in rendered or " citations=\"" in rendered
    source_ref_returned = int(diagnostics.get("source_refs_total") or 0) >= 1 or (
        item_source_ref_count >= 1
    )
    citation_rendered = (
        int(diagnostics.get("citations_rendered") or 0) >= 1
        or item_citation_count >= 1
        or rendered_citation_present
    )
    fallback_grounded = bool(matching_items) and citation_rendered and source_ref_returned
    default_context_excludes_stale = quality.get("default_context_excludes_stale") is True or (
        quality == {} and int(diagnostics.get("superseded_facts_considered") or 0) == 0
    )
    serialized = json.dumps(
        {"approve": approve_payload, "search": search_payload},
        ensure_ascii=False,
        sort_keys=True,
    )
    checks = {
        "approve_ok": approve_payload.get("ok") is True,
        "approved_fact_id_present": isinstance(fact_id, str) and bool(fact_id),
        "search_ok": search_payload.get("ok") is True,
        "canonical_item_found": bool(matching_items) or topic in rendered,
        "citation_rendered": citation_rendered,
        "source_ref_returned": source_ref_returned,
        "answerability_grounded": quality.get("answerability_status") == "grounded"
        or fallback_grounded,
        "response_policy_cites": (
            quality.get("recommended_response_policy") == "answer_with_citations"
            or citation_rendered
        ),
        "default_context_excludes_stale": default_context_excludes_stale,
        "raw_token_absent": token not in serialized,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "approved_fact_id": fact_id,
        "items_returned": len(items),
        "matching_items": len(matching_items),
        "citations_rendered": diagnostics.get("citations_rendered"),
        "source_refs_total": diagnostics.get("source_refs_total"),
        "rendered_citation_present": rendered_citation_present,
        "answerability_status": quality.get("answerability_status")
        or ("grounded" if fallback_grounded else None),
        "recommended_response_policy": quality.get("recommended_response_policy")
        or ("answer_with_citations" if citation_rendered else None),
    }


def _create_capture(
    client: httpx.Client,
    *,
    space_slug: str,
    scope_ref: str,
    marker: str,
) -> dict[str, Any]:
    text = (
        f"Remember: {marker} Project Atlas local MCP visual memory smoke keeps "
        "the first capture, review suggestion and graph browser connected."
    )
    response = client.post(
        "/v1/captures",
        json={
            "space_slug": space_slug,
            "memory_scope_external_ref": scope_ref,
            "source_agent": "local-visual-smoke",
            "source_kind": "manual",
            "event_type": "LocalVisualMemorySmoke",
            "actor_role": "user",
            "text": text,
            "metadata": {"sandbox": True, "marker": marker},
            "idempotency_key": marker,
            "consolidate": True,
        },
    )
    response.raise_for_status()
    return dict(response.json().get("data") or {})


def _wait_for_visual_memory(
    client: httpx.Client,
    *,
    space_slug: str,
    scope_ref: str,
    capture_id: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    last: dict[str, Any] = {}
    while True:
        last = _visual_memory_state(
            client,
            space_slug=space_slug,
            scope_ref=scope_ref,
            capture_id=capture_id,
        )
        if last["ok"] or time.monotonic() >= deadline:
            return last
        time.sleep(0.5)


def _visual_memory_state(
    client: httpx.Client,
    *,
    space_slug: str,
    scope_ref: str,
    capture_id: str,
) -> dict[str, Any]:
    params = {
        "space_slug": space_slug,
        "memory_scope_external_ref": scope_ref,
        "limit": 25,
    }
    captures = _data_list(client.get("/v1/captures", params=params))
    suggestions = _data_list(client.get("/v1/suggestions", params={**params, "status": "pending"}))
    browser_data = dict(client.get("/v1/memory-browser", params=params).json().get("data") or {})
    browser_captures = (
        browser_data.get("captures") if isinstance(browser_data.get("captures"), list) else []
    )
    browser_suggestions = (
        browser_data.get("suggestions") if isinstance(browser_data.get("suggestions"), list) else []
    )
    target_capture = _find_by_id(captures, capture_id)
    browser_capture = _find_by_id(browser_captures, capture_id)
    created_from_capture = [
        suggestion
        for suggestion in suggestions
        if str(suggestion.get("created_from_capture_id") or "") == capture_id
    ]
    return {
        "ok": bool(
            target_capture
            and target_capture.get("consolidation_status") == "consolidated"
            and created_from_capture
            and browser_capture
        ),
        "capture_id": capture_id,
        "capture_consolidation_status": (
            target_capture.get("consolidation_status") if target_capture else None
        ),
        "pending_suggestions": len(suggestions),
        "created_from_capture_suggestions": len(created_from_capture),
        "created_from_capture_suggestion_ids": [
            str(suggestion.get("id"))
            for suggestion in created_from_capture[:5]
            if suggestion.get("id")
        ],
        "browser_capture_visible": bool(browser_capture),
        "browser_suggestions_visible": len(browser_suggestions),
        "browser_stats": (
            browser_data.get("stats") if isinstance(browser_data.get("stats"), dict) else {}
        ),
    }


def _build_report(
    *,
    api_url: str,
    space_slug: str,
    scope_ref: str,
    checks: dict[str, Any],
    failures: list[str],
    started: float,
    run_id: str,
) -> dict[str, Any]:
    report = {
        "suite": SUITE,
        "ok": not failures,
        "strict_local_visual_mcp": True,
        "api_url": api_url,
        "ui_url": f"{api_url}/ui/#capture",
        "review_url": f"{api_url}/ui/#review",
        "space_slug": space_slug,
        "memory_scope_external_ref": scope_ref,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "checks": checks,
        "failures": failures,
    }
    return with_report_provenance(
        report,
        generated_by="scripts/local_mcp_visual_memory_smoke.py",
        suite=SUITE,
        run_id=run_id,
        project="infinity-context",
        cwd=PROJECT_ROOT,
    )


def _failed_required_checks(checks: dict[str, Any]) -> list[str]:
    required = (
        "health",
        "capabilities",
        "ui",
        "ui_assets",
        "generated_mcp",
        "mcp_session",
        "mcp_digest",
        "mcp_reviewed_search",
        "capture_created",
        "visual_memory",
    )
    return [
        name
        for name in required
        if not isinstance(checks.get(name), dict) or checks[name].get("ok") is not True
    ]


def _emit_report(report: dict[str, Any], *, report_out: str, env: dict[str, str]) -> None:
    serialized = json.dumps(redact_payload(report, env=env), ensure_ascii=False, sort_keys=True)
    if has_unredacted_secret_marker(serialized):
        raise LocalVisualSmokeFailure("Refusing to write local visual smoke report with secrets")
    if report_out:
        path = Path(report_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


def _secret_env(token: str) -> dict[str, str]:
    return {
        "MEMORY_MCP_AUTH_TOKEN": token,
        "MEMORY_SERVICE_TOKEN": token,
    }


def _data_list(response: httpx.Response) -> list[dict[str, Any]]:
    response.raise_for_status()
    data = response.json().get("data")
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _find_by_id(items: list[dict[str, Any]], item_id: str) -> dict[str, Any] | None:
    return next((item for item in items if str(item.get("id") or "") == item_id), None)


def _json_at(response: httpx.Response, *keys: str) -> Any:
    try:
        value: Any = response.json()
    except ValueError:
        return None
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


if __name__ == "__main__":
    raise SystemExit(main())
