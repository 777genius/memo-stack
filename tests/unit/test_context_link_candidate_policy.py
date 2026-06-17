from memo_stack_core.application.context_link_candidate_policy import candidate


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

