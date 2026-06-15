from memo_stack_core.application.anchor_extraction import extract_observed_anchors


def test_anchor_extraction_ignores_document_metadata_as_people() -> None:
    anchors = extract_observed_anchors(
        "Content Dimensions Duration Format Streams Transcript Keyframes Page"
    )

    assert {
        (anchor.kind.value, anchor.normalized_key)
        for anchor in anchors
        if anchor.kind.value == "person"
    } == set()


def test_anchor_extraction_keeps_real_people_projects_and_events() -> None:
    anchors = extract_observed_anchors(
        "Alex shared Project Atlas notes from meeting last week about Qdrant."
    )

    keys = {(anchor.kind.value, anchor.normalized_key) for anchor in anchors}
    assert ("person", "alex") in keys
    assert ("project", "atlas") in keys
    assert ("project", "qdrant") in keys
    assert ("event", "meeting last week") in keys
