import json

from scripts.agent_transcript_corpus_redactor import redact_text, redact_transcript_corpus


def test_redact_text_masks_common_agent_transcript_secrets() -> None:
    redacted, counts = redact_text(
        "Use password=bench-secret-value and Authorization: Bearer live-secret-token "
        "with sk-proj-secretvalue1234567890, dev@example.com, "
        "and /Users/alice/dev/private/path."
    )

    assert "bench-secret-value" not in redacted
    assert "live-secret-token" not in redacted
    assert "sk-proj-secretvalue1234567890" not in redacted
    assert "dev@example.com" not in redacted
    assert "/Users/alice" not in redacted
    assert "<redacted:secret>" in redacted
    assert "<redacted:token>" in redacted
    assert "<redacted:email>" in redacted
    assert "/Users/<redacted:path>" in redacted
    assert counts["assignment_secret"] == 1
    assert counts["bearer_token"] == 1
    assert counts["openai_key"] == 1
    assert counts["email"] == 1
    assert counts["home_path"] == 1


def test_redactor_writes_benchmark_fixture_without_source_path_or_raw_secret(
    tmp_path,
) -> None:
    source_dir = tmp_path / "raw"
    source_dir.mkdir()
    output_dir = tmp_path / "redacted"
    raw_file = source_dir / "codex-session.json"
    raw_file.write_text(
        json.dumps(
            {
                "messages": [
                    {"role": "user", "content": "Remember project fact."},
                    {
                        "role": "assistant",
                        "content": (
                            "Durable fact: memory stays evidence. "
                            "password=bench-secret-raw-value. "
                            "/Users/alice/private/repo"
                        ),
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    result = redact_transcript_corpus(
        input_path=source_dir,
        output_dir=output_dir,
        extra_tags=("codex",),
    )

    assert result["ok"] is True
    assert result["written_count"] == 1
    fixture_path = output_dir / result["written_files"][0]
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    rendered = json.dumps(fixture, ensure_ascii=False, sort_keys=True)
    assert "bench-secret-raw-value" not in rendered
    assert "/Users/alice" not in rendered
    assert "codex-session" not in rendered
    assert fixture["expected_tools"] == ["memory_search", "memory_ingest_document"]
    assert fixture["forbidden_contains"] == ["<redacted:path>", "<redacted:secret>"]
    assert "codex" in fixture["tags"]
    assert fixture["metadata"]["manual_annotation_recommended"] is True
    assert fixture["metadata"]["source_suffix"] == ".json"


def test_redactor_reads_jsonl_turns(tmp_path) -> None:
    raw_file = tmp_path / "session.jsonl"
    output_dir = tmp_path / "out"
    raw_file.write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "content": "First turn."}),
                json.dumps({"role": "assistant", "text": "Second turn."}),
            ]
        ),
        encoding="utf-8",
    )

    result = redact_transcript_corpus(input_path=raw_file, output_dir=output_dir)

    fixture = json.loads((output_dir / result["written_files"][0]).read_text(encoding="utf-8"))
    assert "user: First turn." in fixture["transcript"]
    assert "assistant: Second turn." in fixture["transcript"]


def test_redactor_skips_oversized_files(tmp_path) -> None:
    raw_file = tmp_path / "large.txt"
    raw_file.write_text("x" * 20, encoding="utf-8")
    output_dir = tmp_path / "out"

    result = redact_transcript_corpus(
        input_path=raw_file,
        output_dir=output_dir,
        max_bytes=10,
    )

    assert result["written_count"] == 0
    assert result["skipped"] == [{"file": "large.txt", "reason": "file_too_large"}]
