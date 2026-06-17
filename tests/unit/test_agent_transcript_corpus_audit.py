import json

import scripts.agent_transcript_corpus_audit as corpus_audit
from scripts.agent_transcript_corpus_audit import audit_transcript_corpus


def test_corpus_audit_accepts_ready_fixture(tmp_path) -> None:
    _write_fixture(
        tmp_path / "ready.json",
        {
            "id": "ready",
            "transcript": "agent: durable memory must be evidence only",
            "expected_tools": ["memory_search", "memory_ingest_document"],
            "expected_answer_contains": ["evidence only"],
            "forbidden_contains": [],
            "metadata": {"source_sha256": "a" * 64},
        },
    )

    report = audit_transcript_corpus(tmp_path, strict=True)

    assert report["ok"] is True
    assert report["file_count"] == 1
    assert report["ready_count"] == 1
    assert report["needs_annotation_count"] == 0
    assert report["unsafe_count"] == 0
    assert report["files"][0]["status"] == "ready"


def test_corpus_audit_warns_when_fixture_needs_manual_annotation(tmp_path) -> None:
    _write_fixture(
        tmp_path / "needs-annotation.json",
        {
            "id": "needs-annotation",
            "transcript": "agent: durable memory must be evidence only",
            "expected_tools": ["memory_search", "memory_ingest_document"],
            "forbidden_contains": [],
            "metadata": {
                "source_sha256": "b" * 64,
                "manual_annotation_recommended": True,
            },
        },
    )

    advisory = audit_transcript_corpus(tmp_path, strict=False)
    strict = audit_transcript_corpus(tmp_path, strict=True)

    assert advisory["ok"] is True
    assert strict["ok"] is False
    assert strict["needs_annotation_count"] == 1
    assert strict["files"][0]["status"] == "needs_annotation"
    assert "needs_high_signal_expected_checks" in strict["files"][0]["warnings"]


def test_corpus_audit_rejects_unredacted_secret_patterns(tmp_path) -> None:
    _write_fixture(
        tmp_path / "unsafe.json",
        {
            "id": "unsafe",
            "transcript": "assistant: token=sk-svcacct-abcdefghijklmnopqrstuvwxyz1234567890",
            "expected_tools": ["memory_search"],
            "expected_answer_contains": ["anything"],
            "forbidden_contains": [],
            "metadata": {"source_sha256": "c" * 64},
        },
    )

    report = audit_transcript_corpus(tmp_path, strict=False)

    assert report["ok"] is False
    assert report["unsafe_count"] == 1
    assert report["files"][0]["status"] == "unsafe"
    assert "contains_unredacted_sensitive_pattern" in report["files"][0]["failures"]


def test_corpus_audit_warns_when_redacted_markers_are_not_forbidden(tmp_path) -> None:
    _write_fixture(
        tmp_path / "marker.json",
        {
            "id": "marker",
            "transcript": "assistant: token=<redacted:secret>",
            "expected_tools": ["memory_search"],
            "expected_answer_contains": ["token"],
            "forbidden_contains": [],
            "metadata": {"source_sha256": "d" * 64},
        },
    )

    report = audit_transcript_corpus(tmp_path, strict=True)

    assert report["ok"] is True
    assert "redacted_markers_should_be_forbidden_contains" in report["files"][0]["warnings"]


def test_corpus_audit_main_redacts_exception(capsys, monkeypatch, tmp_path) -> None:
    raw_secret = "sk-svcacct-abcdefghijklmnopqrstuvwxyz1234567890"

    def fail_audit(*_args, **_kwargs):
        raise RuntimeError(f"failed with {raw_secret}")

    monkeypatch.setattr(corpus_audit, "audit_transcript_corpus", fail_audit)

    exit_code = corpus_audit.main([str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert raw_secret not in captured.err
    assert "<redacted:secret>" in captured.err


def _write_fixture(path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")
