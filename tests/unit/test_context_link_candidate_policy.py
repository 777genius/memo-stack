from memo_stack_core.application.context_link_candidate_policy import (
    _MAX_QUERY_TERM_CHARS,
    _MAX_QUERY_TERMS,
    candidate,
    candidate_metadata,
    evidence_summary,
    terms,
)
from memo_stack_core.domain.entities import SourceRef


def test_candidate_reason_codes_keep_specific_rule_signals() -> None:
    item = candidate(
        target_type="anchor",
        target_id="anchor_alex",
        label="person: Alex",
        preview="Alex",
        score=72,
        reasons=[
            "person name",
            "explicit project reference",
            "known project/tool reference",
            "event phrase",
            "organization reference",
        ],
        metadata={},
    )

    assert item.metadata["reason_codes"] == [
        "person_name",
        "explicit_project_reference",
        "known_project_tool_reference",
        "event_phrase",
        "organization_reference",
    ]


def test_query_terms_are_bounded_and_redacted_before_diagnostics() -> None:
    long_token = "x" * (_MAX_QUERY_TERM_CHARS + 24)
    raw_terms = [f"unique_term_{index}" for index in range(_MAX_QUERY_TERMS + 25)]
    raw_terms.insert(5, "sk-proj-secretvalue1234567890")
    raw_terms.insert(6, long_token)

    result = terms(" ".join(raw_terms))

    assert len(result) == _MAX_QUERY_TERMS
    assert "sk-proj-secretvalue1234567890" not in result
    assert "[redacted]" not in result
    assert long_token[:_MAX_QUERY_TERM_CHARS] in result
    assert all(len(item) <= _MAX_QUERY_TERM_CHARS for item in result)


def test_evidence_summary_is_bounded_and_multimodal_without_quotes() -> None:
    refs = tuple(
        SourceRef(
            source_type="asset_extraction",
            source_id=f"extract-{index}.png",
            chunk_id=f"chunk-{index}",
            char_start=index,
            char_end=index + 10,
            quote_preview="raw OCR text should not be copied",
            page_number=1 if index == 0 else None,
            time_start_ms=1000 if index == 1 else None,
            time_end_ms=2500 if index == 1 else None,
            bbox=(0.0, 1.0, 120.0, 40.0) if index == 2 else None,
        )
        for index in range(7)
    )

    summary = evidence_summary(refs)

    assert summary["evidence_source_ref_count"] == 7
    assert summary["evidence_source_refs_returned"] == 5
    assert summary["evidence_source_refs_truncated"] is True
    assert summary["evidence_source_types"] == ["asset_extraction"]
    assert set(summary["evidence_modalities"]) == {"document", "image", "time_range"}
    assert summary["evidence_has_page_ref"] is True
    assert summary["evidence_has_bbox_ref"] is True
    assert summary["evidence_has_time_range_ref"] is True
    evidence_refs = summary["evidence_refs"]
    assert len(evidence_refs) == 5
    assert evidence_refs[0]["page_number"] == 1
    assert evidence_refs[1]["time_start_ms"] == 1000
    assert evidence_refs[2]["bbox"] == [0.0, 1.0, 120.0, 40.0]
    assert "quote_preview" not in evidence_refs[0]


def test_candidate_metadata_preserves_bounded_evidence_refs_for_review_history() -> None:
    item = candidate(
        target_type="chunk",
        target_id="chunk-1",
        label="document #1",
        preview="safe preview",
        score=82,
        reasons=["matching text"],
        metadata={
            **evidence_summary(
                (
                    SourceRef(
                        source_type="asset_extraction",
                        source_id="extract-1",
                        chunk_id="chunk-1",
                        page_number=2,
                    ),
                )
            ),
            "raw_private_payload": [{"secret": "must be ignored"}],
        },
    )

    metadata = candidate_metadata(item, {"resolver_version": "test-resolver"})

    assert metadata["resolver_version"] == "test-resolver"
    assert metadata["evidence_source_ref_count"] == 1
    assert metadata["evidence_refs"] == [
        {
            "source_type": "asset_extraction",
            "source_id": "extract-1",
            "chunk_id": "chunk-1",
            "page_number": 2,
        }
    ]
    assert "raw_private_payload" not in metadata
