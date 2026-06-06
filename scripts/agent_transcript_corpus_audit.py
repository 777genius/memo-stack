"""Audit redacted agent transcript benchmark corpus fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.agent_transcript_corpus_redactor import redact_text
except ModuleNotFoundError:
    from agent_transcript_corpus_redactor import redact_text

REQUIRED_SEARCH_TOOL = "memory_search"
READINESS_CHECK_KEYS = (
    "required_memory_checks",
    "expected_answer_contains",
    "expected_memory_contains",
)
REDACTED_MARKERS = (
    "<redacted:email>",
    "<redacted:path>",
    "<redacted:secret>",
    "<redacted:token>",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus_dir", type=Path, help="Directory with redacted corpus JSON files")
    parser.add_argument("--strict", action="store_true", help="Fail when fixtures need annotation")
    args = parser.parse_args(argv)

    try:
        report = audit_transcript_corpus(args.corpus_dir, strict=args.strict)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0 if report["ok"] else 1


def audit_transcript_corpus(corpus_dir: Path, *, strict: bool = False) -> dict[str, Any]:
    root = corpus_dir.expanduser()
    if not root.is_dir():
        raise ValueError("corpus_dir must point to a directory")
    files = sorted(path for path in root.iterdir() if path.is_file() and path.suffix == ".json")
    items = [_audit_fixture(path) for path in files]
    unsafe_count = sum(1 for item in items if item["status"] == "unsafe")
    ready_count = sum(1 for item in items if item["release_gate_ready"])
    needs_annotation_count = sum(1 for item in items if item["needs_annotation"])
    ok = unsafe_count == 0 and (not strict or needs_annotation_count == 0)
    return {
        "ok": ok,
        "strict": strict,
        "file_count": len(items),
        "ready_count": ready_count,
        "needs_annotation_count": needs_annotation_count,
        "unsafe_count": unsafe_count,
        "files": items,
    }


def _audit_fixture(path: Path) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _file_report(path, status="unsafe", failures=["invalid_json"])
    if not isinstance(payload, dict):
        return _file_report(path, status="unsafe", failures=["root_must_be_object"])

    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    redacted, redaction_counts = redact_text(rendered)
    if redacted != rendered:
        failures.append("contains_unredacted_sensitive_pattern")
    transcript = payload.get("transcript") or payload.get("text")
    if not isinstance(transcript, str) or not transcript.strip():
        failures.append("missing_transcript_text")
    expected_tools = _string_list(payload.get("expected_tools"))
    if REQUIRED_SEARCH_TOOL not in expected_tools:
        warnings.append("expected_tools_should_include_memory_search")
    if not _has_readiness_checks(payload):
        warnings.append("needs_high_signal_expected_checks")
    if _redacted_markers_in_text(transcript) - set(_string_list(payload.get("forbidden_contains"))):
        warnings.append("redacted_markers_should_be_forbidden_contains")
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        if metadata.get("manual_annotation_recommended") is True:
            warnings.append("manual_annotation_recommended")
        if not isinstance(metadata.get("source_sha256"), str):
            warnings.append("missing_source_sha256")
    else:
        warnings.append("missing_metadata")

    needs_annotation = "needs_high_signal_expected_checks" in warnings
    status = "unsafe" if failures else ("needs_annotation" if needs_annotation else "ready")
    return _file_report(
        path,
        status=status,
        failures=failures,
        warnings=warnings,
        redaction_counts=redaction_counts,
        release_gate_ready=status == "ready",
        needs_annotation=needs_annotation,
    )


def _has_readiness_checks(payload: dict[str, Any]) -> bool:
    for key in READINESS_CHECK_KEYS:
        value = payload.get(key)
        if isinstance(value, list) and any(isinstance(item, (dict, str)) for item in value):
            return True
        if isinstance(value, str) and value.strip():
            return True
    return False


def _redacted_markers_in_text(value: object) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {marker for marker in REDACTED_MARKERS if marker in value}


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _file_report(
    path: Path,
    *,
    status: str,
    failures: list[str],
    warnings: list[str] | None = None,
    redaction_counts: dict[str, int] | None = None,
    release_gate_ready: bool = False,
    needs_annotation: bool = False,
) -> dict[str, Any]:
    return {
        "file": path.name,
        "status": status,
        "release_gate_ready": release_gate_ready,
        "needs_annotation": needs_annotation,
        "failures": failures,
        "warnings": warnings or [],
        "redaction_counts": redaction_counts or {},
    }


if __name__ == "__main__":
    raise SystemExit(main())
