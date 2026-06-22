from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "local_mcp_visual_memory_smoke.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "local_mcp_visual_memory_smoke_for_test",
        SCRIPT_PATH,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_visual_smoke_report_redacts_tokens(tmp_path: Path, capsys) -> None:
    module = _load_module()
    token = "unit-local-visual-secret-token"
    report = module._build_report(
        api_url="http://127.0.0.1:17788",
        space_slug="unit-local-visual",
        scope_ref="unit-scope",
        checks={
            "health": {"ok": True},
            "capabilities": {"ok": True},
            "ui": {"ok": True},
            "ui_assets": {"ok": True},
            "generated_mcp": {"ok": True, "token": token},
            "mcp_session": {"ok": True},
            "mcp_digest": {
                "ok": True,
                "checks": {
                    "evidence_only": True,
                    "pending_suggestion_visible": True,
                    "raw_token_absent": True,
                },
            },
            "mcp_reviewed_search": {
                "ok": True,
                "checks": {
                    "answerability_grounded": True,
                    "citation_rendered": True,
                    "source_ref_returned": True,
                    "raw_token_absent": True,
                },
            },
            "capture_created": {"ok": True},
            "visual_memory": {"ok": True},
        },
        failures=[],
        started=0.0,
        run_id="unit-run",
    )

    report_out = tmp_path / "local-visual.json"
    module._emit_report(report, report_out=str(report_out), env=module._secret_env(token))

    rendered = report_out.read_text(encoding="utf-8")
    stdout = capsys.readouterr().out
    payload = json.loads(rendered)
    assert payload["suite"] == module.SUITE
    assert payload["ok"] is True
    assert token not in rendered
    assert token not in stdout
    assert "<redacted" in rendered


def test_local_visual_smoke_required_checks_are_hard_gate() -> None:
    module = _load_module()

    assert module._failed_required_checks(
        {
            "health": {"ok": True},
            "capabilities": {"ok": True},
            "ui": {"ok": True},
            "ui_assets": {"ok": True},
            "generated_mcp": {"ok": True},
            "mcp_session": {"ok": False},
            "mcp_digest": {"ok": True},
            "mcp_reviewed_search": {"ok": True},
            "capture_created": {"ok": True},
            "visual_memory": {"ok": True},
        }
    ) == ["mcp_session"]

    assert module._failed_required_checks(
        {
            "health": {"ok": True},
            "capabilities": {"ok": True},
            "ui": {"ok": True},
            "ui_assets": {"ok": True},
            "generated_mcp": {"ok": True},
            "mcp_session": {"ok": True},
            "mcp_digest": {"ok": False},
            "mcp_reviewed_search": {"ok": True},
            "capture_created": {"ok": True},
            "visual_memory": {"ok": True},
        }
    ) == ["mcp_digest"]

    assert module._failed_required_checks(
        {
            "health": {"ok": True},
            "capabilities": {"ok": True},
            "ui": {"ok": True},
            "ui_assets": {"ok": True},
            "generated_mcp": {"ok": True},
            "mcp_session": {"ok": True},
            "mcp_digest": {"ok": True},
            "mcp_reviewed_search": {"ok": False},
            "capture_created": {"ok": True},
            "visual_memory": {"ok": True},
        }
    ) == ["mcp_reviewed_search"]


def test_local_visual_smoke_requires_first_memory_guidance() -> None:
    module = _load_module()

    class Response:
        def __init__(self, *, status_code=200, text="", payload=None):
            self.status_code = status_code
            self.text = text
            self._payload = payload if payload is not None else {}

        @property
        def is_success(self):
            return 200 <= self.status_code < 300

        def json(self):
            return self._payload

    class Client:
        def get(self, path):
            if path == "/v1/health":
                return Response(payload={"status": "ok"})
            if path == "/v1/capabilities":
                return Response(payload={"suggestions": {"review_tool_supported": True}})
            if path == "/ui/":
                return Response(
                    text=(
                        "Infinity Context Browser "
                        "first-memory-rail "
                        "firstMemoryNextStep "
                        "firstMemoryEvidenceKinds "
                        "firstMemoryReviewState"
                    )
                )
            if path == "/ui/assets/memory-browser.js":
                return Response(
                    text=(
                        "renderFirstMemoryRail "
                        "firstMemoryEvidenceLabels "
                        "activeExtractionModalities "
                        "tabNameFromHash"
                    )
                )
            raise AssertionError(path)

    checks = module._check_http_surfaces(Client())

    assert checks["ui"]["ok"] is False
    assert checks["ui"]["first_memory_guidance"] is False
    assert checks["ui_assets"]["ok"] is True


def test_local_visual_smoke_summarizes_mcp_digest_as_evidence_only() -> None:
    module = _load_module()
    token = "unit-local-visual-secret-token"
    topic = "LOCAL_VISUAL_MCP_SMOKE_unit"
    payload = {
        "ok": True,
        "data": {
            "digest_id": "dig_unit",
            "topic": topic,
            "rendered_markdown": (
                "# Memory Digest\n"
                "Evidence only: true\n"
                f"- [suggestion:sug_unit, score=0.50, not_canonical] text=\"{topic}\""
            ),
            "sections": [
                {
                    "title": "Pending suggestions",
                    "items": [{"id": "sug_unit", "text": f"{topic} pending review"}],
                }
            ],
            "diagnostics": {
                "evidence_only": True,
                "pending_suggestions_considered": 1,
            },
        },
    }

    summary = module._summarize_mcp_digest_payload(
        payload=payload,
        topic=topic,
        token=token,
    )

    assert summary["ok"] is True
    assert summary["digest_id"] == "dig_unit"
    assert summary["pending_suggestion_items"] == 1
    assert summary["checks"]["raw_token_absent"] is True


def test_local_visual_smoke_rejects_digest_without_pending_review_evidence() -> None:
    module = _load_module()
    topic = "LOCAL_VISUAL_MCP_SMOKE_unit"

    summary = module._summarize_mcp_digest_payload(
        payload={
            "ok": True,
            "data": {
                "digest_id": "dig_unit",
                "topic": topic,
                "rendered_markdown": "Evidence only: true",
                "sections": [],
                "diagnostics": {
                    "evidence_only": True,
                    "pending_suggestions_considered": 0,
                },
            },
        },
        topic=topic,
        token="unit-token",
    )

    assert summary["ok"] is False
    assert summary["checks"]["pending_suggestion_visible"] is False
    assert summary["checks"]["pending_suggestions_considered"] is False


def test_local_visual_smoke_summarizes_reviewed_search_as_grounded_evidence() -> None:
    module = _load_module()
    token = "unit-local-visual-secret-token"
    topic = "LOCAL_VISUAL_MCP_SMOKE_unit"
    approve_payload = {
        "ok": True,
        "data": {"fact": {"id": "fact_unit", "text": topic}},
    }
    search_payload = {
        "ok": True,
        "data": {
            "rendered_text": f"[1] fact:fact_unit text=\"{topic}\"",
            "items": [
                {
                    "item_id": "fact_unit",
                    "text": topic,
                    "source_refs": [{"source_type": "capture:manual", "source_id": "cap_unit"}],
                    "citations": [{"citation_id": "cit_unit"}],
                }
            ],
            "diagnostics": {
                "citations_rendered": 1,
                "source_refs_total": 1,
                "retrieval_quality_summary": {
                    "answerability_status": "grounded",
                    "recommended_response_policy": "answer_with_citations",
                    "default_context_excludes_stale": True,
                },
            },
        },
    }

    summary = module._summarize_mcp_reviewed_search_payload(
        approve_payload=approve_payload,
        search_payload=search_payload,
        topic=topic,
        token=token,
    )

    assert summary["ok"] is True
    assert summary["approved_fact_id"] == "fact_unit"
    assert summary["items_returned"] == 1
    assert summary["checks"]["citation_rendered"] is True
    assert summary["checks"]["source_ref_returned"] is True
    assert summary["recommended_response_policy"] == "answer_with_citations"


def test_local_visual_smoke_accepts_public_mcp_search_payload_shape() -> None:
    module = _load_module()
    topic = "LOCAL_VISUAL_MCP_SMOKE_public"

    summary = module._summarize_mcp_reviewed_search_payload(
        approve_payload={"ok": True, "data": {"fact": {"id": "fact_public"}}},
        search_payload={
            "ok": True,
            "data": {
                "rendered_text": (
                    f"[1] fact:fact_public citations=\"capture-manual:cap_public\" "
                    f"text=\"{topic}\""
                ),
                "items": [
                    {
                        "item_id": "fact_public",
                        "text": topic,
                        "source_refs": [
                            {
                                "source_type": "capture:manual",
                                "source_id": "cap_public",
                            }
                        ],
                    }
                ],
                "diagnostics": {"superseded_facts_considered": 0},
            },
        },
        topic=topic,
        token="unit-token",
    )

    assert summary["ok"] is True
    assert summary["rendered_citation_present"] is True
    assert summary["answerability_status"] == "grounded"
    assert summary["recommended_response_policy"] == "answer_with_citations"


def test_local_visual_smoke_rejects_reviewed_search_without_citation() -> None:
    module = _load_module()
    topic = "LOCAL_VISUAL_MCP_SMOKE_unit"

    summary = module._summarize_mcp_reviewed_search_payload(
        approve_payload={"ok": True, "data": {"fact": {"id": "fact_unit"}}},
        search_payload={
            "ok": True,
            "data": {
                "rendered_text": topic,
                "items": [{"item_id": "fact_unit", "text": topic}],
                "diagnostics": {
                    "citations_rendered": 0,
                    "source_refs_total": 0,
                    "retrieval_quality_summary": {
                        "answerability_status": "grounded",
                        "recommended_response_policy": "answer_with_citations",
                        "default_context_excludes_stale": True,
                    },
                },
            },
        },
        topic=topic,
        token="unit-token",
    )

    assert summary["ok"] is False
    assert summary["checks"]["citation_rendered"] is False
    assert summary["checks"]["source_ref_returned"] is False


def test_local_visual_state_requires_consolidated_capture_and_pending_review() -> None:
    module = _load_module()

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return self._payload

    class Client:
        def get(self, path, params=None):
            if path == "/v1/captures":
                return Response(
                    {
                        "data": [
                            {
                                "id": "cap_unit",
                                "consolidation_status": "consolidated",
                            }
                        ]
                    }
                )
            if path == "/v1/suggestions":
                return Response(
                    {
                        "data": [
                            {
                                "id": "sug_unit",
                                "status": "pending",
                                "created_from_capture_id": "cap_unit",
                            }
                        ]
                    }
                )
            if path == "/v1/memory-browser":
                return Response(
                    {
                        "data": {
                            "captures": [{"id": "cap_unit"}],
                            "stats": {"captures": 1},
                        }
                    }
                )
            raise AssertionError(path)

    state = module._visual_memory_state(
        Client(),
        space_slug="unit",
        scope_ref="scope",
        capture_id="cap_unit",
    )

    assert state["ok"] is True
    assert state["created_from_capture_suggestions"] == 1
    assert state["browser_capture_visible"] is True


def test_local_visual_capture_payload_uses_allowed_manual_source_kind() -> None:
    module = _load_module()
    sent_payloads = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"data": {"id": "cap_unit"}}

    class Client:
        def post(self, path, json):
            sent_payloads.append((path, json))
            return Response()

    module._create_capture(
        Client(),
        space_slug="unit",
        scope_ref="scope",
        marker="MARKER",
    )

    assert sent_payloads[0][0] == "/v1/captures"
    assert sent_payloads[0][1]["source_kind"] == "manual"
    assert sent_payloads[0][1]["actor_role"] == "user"


def test_local_visual_report_redacts_openai_like_secret_marker(tmp_path: Path) -> None:
    module = _load_module()
    report_out = tmp_path / "safe.json"
    secret = "sk-unitsecret_12345678901234567890"

    module._emit_report({"leak": secret}, report_out=str(report_out), env={})

    rendered = report_out.read_text(encoding="utf-8")
    assert secret not in rendered
    assert "<redacted>" in rendered
