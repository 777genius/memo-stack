from memo_stack_core.application.context_link_candidate_policy import (
    _MAX_QUERY_TERM_CHARS,
    _MAX_QUERY_TERMS,
    candidate,
    terms,
)


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
