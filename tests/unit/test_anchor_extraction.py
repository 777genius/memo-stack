from infinity_context_core.application.anchor_extraction import extract_observed_anchors


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


def test_anchor_extraction_ignores_temporal_leading_words_as_people() -> None:
    anchors = extract_observed_anchors(
        "Yesterday Alex met Dana about Project Atlas billing cutoff."
    )

    keys = {(anchor.kind.value, anchor.normalized_key) for anchor in anchors}
    person_keys = {anchor.normalized_key for anchor in anchors if anchor.kind.value == "person"}
    event_keys = {anchor.normalized_key for anchor in anchors if anchor.kind.value == "event"}
    assert ("person", "alex") in keys
    assert ("person", "dana") in keys
    assert ("project", "atlas") in keys
    assert "yesterday alex" not in person_keys
    assert "met with alex yesterday" in event_keys


def test_anchor_extraction_handles_russian_project_case_inflections() -> None:
    anchors = extract_observed_anchors(
        "На прошлой неделе был созвон с Алексом по проекту Атлас."
    )

    keys = {(anchor.kind.value, anchor.normalized_key) for anchor in anchors}
    person_keys = {anchor.normalized_key for anchor in anchors if anchor.kind.value == "person"}
    event_keys = {anchor.normalized_key for anchor in anchors if anchor.kind.value == "event"}
    assert ("project", "атлас") in keys
    assert ("person", "алекс") in keys
    assert "атлас" not in person_keys
    assert "созвон с алексом на прошлой неделе" in event_keys


def test_anchor_extraction_ignores_command_verbs_as_people() -> None:
    anchors = extract_observed_anchors(
        "Open the Docker backend logs and screenshot progress bar."
    )

    person_keys = {anchor.normalized_key for anchor in anchors if anchor.kind.value == "person"}
    assert "open" not in person_keys


def test_anchor_extraction_keeps_same_name_people_and_projects_separate() -> None:
    anchors = extract_observed_anchors("Alex wrote that Project Alex is a separate workspace.")

    keys = {(anchor.kind.value, anchor.normalized_key) for anchor in anchors}
    assert ("person", "alex") in keys
    assert ("project", "alex") in keys


def test_anchor_extraction_keeps_multi_token_project_names_without_description() -> None:
    anchors = extract_observed_anchors(
        "Project Atlas Mobile tracks onboarding copy. Project Atlas uses Qdrant chunks."
    )

    project_keys = {anchor.normalized_key for anchor in anchors if anchor.kind.value == "project"}
    assert "atlas mobile" in project_keys
    assert "atlas" in project_keys
    assert "atlas mobile tracks" not in project_keys
    assert "atlas uses" not in project_keys


def test_anchor_extraction_stops_project_labels_at_sentence_boundaries() -> None:
    anchors = extract_observed_anchors(
        "Алекс Project Atlas. Час назад я переписывался с Алексом по Project Atlas."
    )

    project_keys = {anchor.normalized_key for anchor in anchors if anchor.kind.value == "project"}
    assert "atlas" in project_keys
    assert "atlas алекс" not in project_keys
    assert "atlas час" not in project_keys


def test_anchor_extraction_keeps_organizations_separate_from_people() -> None:
    anchors = extract_observed_anchors(
        "Alex shared OpenAI notes with company Acme Corp and GitHub team updates."
    )

    keys = {(anchor.kind.value, anchor.normalized_key) for anchor in anchors}
    person_keys = {anchor.normalized_key for anchor in anchors if anchor.kind.value == "person"}
    assert ("person", "alex") in keys
    assert ("organization", "openai") in keys
    assert ("organization", "github") in keys
    assert ("organization", "acme corp") in keys
    assert "openai" not in person_keys
    assert "github" not in person_keys


def test_anchor_extraction_avoids_suffixed_organization_person_false_positives() -> None:
    anchors = extract_observed_anchors(
        "GitHub Actions failed for OpenAI evals. Acme Research LLC owns the rollout. "
        "The GitHub team reviewed OpenAI memory notes."
    )

    keys = {(anchor.kind.value, anchor.normalized_key) for anchor in anchors}
    person_keys = {anchor.normalized_key for anchor in anchors if anchor.kind.value == "person"}
    organization_keys = {
        anchor.normalized_key for anchor in anchors if anchor.kind.value == "organization"
    }

    assert ("organization", "github") in keys
    assert ("organization", "openai") in keys
    assert ("organization", "acme research llc") in keys
    assert "acme research" not in person_keys
    assert "github actions" not in person_keys
    assert "reviewed openai memory notes" not in organization_keys


def test_anchor_extraction_keeps_numeric_temporal_event_labels() -> None:
    anchors = extract_observed_anchors(
        "Сохрани заметку из разговора 5 часов назад и chat 2 days ago."
    )

    keys = {(anchor.kind.value, anchor.normalized_key) for anchor in anchors}
    assert ("event", "разговора 5 часов назад") in keys
    assert ("event", "chat 2 days ago") in keys


def test_anchor_extraction_keeps_event_participants() -> None:
    anchors = extract_observed_anchors(
        "Call with Alex about Atlas. Созвон с Марией вчера по Project Atlas."
    )

    keys = {(anchor.kind.value, anchor.normalized_key) for anchor in anchors}
    canonical_keys = {
        anchor.normalized_key: anchor.metadata.get("canonical_key")
        for anchor in anchors
        if anchor.kind.value == "event"
    }
    assert ("event", "call with alex") in keys
    assert ("event", "созвон с марией вчера") in keys
    assert ("event", "созвон вчера") in keys
    assert canonical_keys["созвон с марией вчера"] == "sozvon s mariya vchera"


def test_anchor_extraction_keeps_event_participant_before_keyword() -> None:
    anchors = extract_observed_anchors(
        "Alex call last week covered billing. Мария созвон вчера подтвердила backend."
    )

    event_keys = {anchor.normalized_key for anchor in anchors if anchor.kind.value == "event"}
    canonical_keys = {
        anchor.normalized_key: anchor.metadata.get("canonical_key")
        for anchor in anchors
        if anchor.kind.value == "event"
    }
    assert "call with alex last week" in event_keys
    assert "созвон с мария вчера" in event_keys
    assert canonical_keys["call with alex last week"] == "call with aleks last week"
    assert canonical_keys["созвон с мария вчера"] == "sozvon s mariya vchera"


def test_anchor_extraction_does_not_attach_next_event_participant() -> None:
    anchors = extract_observed_anchors(
        "Meeting last week and chat with Alex an hour ago covered Project Atlas."
    )

    event_keys = {anchor.normalized_key for anchor in anchors if anchor.kind.value == "event"}
    assert "meeting last week" in event_keys
    assert "meeting with alex last week" not in event_keys
    assert "chat with alex an hour ago" in event_keys


def test_anchor_extraction_handles_russian_temporal_person_cases() -> None:
    anchors = extract_observed_anchors(
        "Час назад я переписывался с Алексом по Project Atlas. Созвон с Марией вчера про backend."
    )

    person_keys = {
        (anchor.normalized_key, anchor.metadata.get("canonical_key"))
        for anchor in anchors
        if anchor.kind.value == "person"
    }
    event_keys = {anchor.normalized_key for anchor in anchors if anchor.kind.value == "event"}
    assert ("час", "chas") not in person_keys
    assert ("созвон", "sozvon") not in person_keys
    assert ("алекс", "aleks") in person_keys
    assert ("мария", "mariya") in person_keys
    assert "переписывался с алексом час назад" in event_keys
    assert "созвон с марией вчера" in event_keys


def test_anchor_extraction_merges_common_russian_person_case_variants() -> None:
    anchors = extract_observed_anchors(
        "Мария подтвердила Project Atlas. От Марии пришел follow-up. "
        "Сергей owns backend. От Сергея пришел Qdrant note. "
        "Алекс согласовал timeline. От Алекса пришел update."
    )

    person_keys = {
        anchor.normalized_key: anchor.metadata.get("canonical_key")
        for anchor in anchors
        if anchor.kind.value == "person"
    }

    assert person_keys["мария"] == "mariya"
    assert person_keys["сергей"] == "sergei"
    assert person_keys["алекс"] == "aleks"
    assert "марии" not in person_keys
    assert "сергея" not in person_keys
    assert "алекса" not in person_keys


def test_anchor_extraction_structures_event_identity_metadata() -> None:
    anchors = extract_observed_anchors(
        "Alex call 2 hours ago covered Project Atlas. "
        "Планерка с Сергеем на прошлой неделе по Project Orion."
    )

    events = {
        anchor.normalized_key: anchor.metadata
        for anchor in anchors
        if anchor.kind.value == "event"
    }

    call = events["call with alex 2 hours ago"]
    assert call["anchor_family"] == "event"
    assert call["event_type"] == "call"
    assert call["event_participant_label"] == "alex"
    assert call["event_participant_canonical_key"] == "aleks"
    assert call["event_temporal_phrase"] == "2 hours ago"
    assert call["event_temporal_hint_code"] == "hours_ago"
    assert call["event_temporal_quantity"] == 2
    assert call["event_temporal_unit"] == "hour"
    assert call["event_identity_terms"] == ["call", "aleks", "hours_ago:2:hour"]

    planning = events["планерка с сергеем на прошлой неделе"]
    assert planning["event_type"] == "планерка"
    assert planning["event_participant_label"] == "сергеем"
    assert planning["event_participant_canonical_key"] == "sergei"
    assert planning["event_temporal_hint_code"] == "last_week"
    assert planning["event_identity_terms"] == [
        "planerka",
        "sergei",
        "last_week:1:week",
    ]


def test_anchor_extraction_structures_people_projects_and_organizations() -> None:
    anchors = extract_observed_anchors(
        "Alex discussed Project Atlas with OpenAI team."
    )

    by_key = {
        (anchor.kind.value, anchor.normalized_key): anchor.metadata
        for anchor in anchors
    }

    assert by_key[("person", "alex")]["person_canonical_key"] == "aleks"
    assert by_key[("project", "atlas")]["project_canonical_key"] == "atlas"
    assert by_key[("organization", "openai")]["organization_canonical_key"] == "openai"
