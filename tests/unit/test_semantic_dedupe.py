from infinity_context_core.application.semantic_dedupe import (
    describe_conflicting_fact_match,
    describe_duplicate_fact_match,
    looks_conflicting_fact,
    looks_equivalent_fact,
    normalize_memory_text,
    semantic_memory_terms,
)


def test_semantic_dedupe_recognizes_document_vector_paraphrase() -> None:
    assert looks_equivalent_fact(
        "Docs retrieval should use Qdrant vectors.",
        "Qdrant owns document vector retrieval.",
    )
    match = describe_duplicate_fact_match(
        "Docs retrieval should use Qdrant vectors.",
        "Qdrant owns document vector retrieval.",
    )
    assert match is not None
    assert match.match_type == "semantic_token_overlap"
    assert "semantic_duplicate" in match.reason_codes


def test_semantic_dedupe_rejects_exclusive_engine_mismatch() -> None:
    assert not looks_equivalent_fact(
        "Docs retrieval should use Qdrant vectors.",
        "Postgres owns document vector retrieval.",
    )


def test_semantic_dedupe_rejects_similar_but_different_project() -> None:
    assert not looks_equivalent_fact(
        "Project Atlas uses Qdrant retrieval for documents.",
        "Project Beta uses Qdrant retrieval for documents.",
    )
    assert not looks_conflicting_fact(
        "Project Atlas uses Qdrant retrieval for documents.",
        "Project Beta uses Qdrant retrieval for documents.",
    )
    assert not looks_equivalent_fact(
        "проект Атлас использует Qdrant для документов.",
        "проект Бета использует Qdrant для документов.",
    )


def test_semantic_dedupe_rejects_similar_but_different_person_event() -> None:
    assert not looks_equivalent_fact(
        "Alex call last week covered Project Atlas pricing.",
        "Maria call last week covered Project Atlas pricing.",
    )
    assert not looks_conflicting_fact(
        "Alex call last week covered Project Atlas pricing.",
        "Maria call last week covered Project Atlas pricing.",
    )


def test_semantic_dedupe_rejects_similar_but_different_event_time() -> None:
    assert not looks_equivalent_fact(
        "Alex call yesterday covered Project Atlas pricing.",
        "Alex call last week covered Project Atlas pricing.",
    )
    assert not looks_conflicting_fact(
        "Alex call yesterday covered Project Atlas pricing.",
        "Alex call last week covered Project Atlas pricing.",
    )
    assert not looks_equivalent_fact(
        "Час назад переписывался с Алексом по Project Atlas pricing.",
        "На прошлой неделе переписывался с Алексом по Project Atlas pricing.",
    )


def test_semantic_dedupe_rejects_numeric_value_mismatch_as_duplicate() -> None:
    assert not looks_equivalent_fact(
        "Project Atlas keeps billing logs for 7 days.",
        "Project Atlas keeps billing logs for 30 days.",
    )
    assert looks_conflicting_fact(
        "Project Atlas keeps billing logs for 7 days.",
        "Project Atlas keeps billing logs for 30 days.",
    )
    match = describe_conflicting_fact_match(
        "Project Atlas keeps billing logs for 7 days.",
        "Project Atlas keeps billing logs for 30 days.",
    )
    assert match is not None
    assert match.match_type == "numeric_value_mismatch"
    assert "numeric_value_mismatch" in match.reason_codes


def test_semantic_dedupe_rejects_version_value_mismatch_as_duplicate() -> None:
    assert not looks_equivalent_fact(
        "Project Atlas API uses model v2 for routing.",
        "Project Atlas API uses model v3 for routing.",
    )
    assert looks_conflicting_fact(
        "Project Atlas API uses model v2 for routing.",
        "Project Atlas API uses model v3 for routing.",
    )


def test_semantic_dedupe_keeps_exact_numeric_fact_duplicate() -> None:
    match = describe_duplicate_fact_match(
        "Project Atlas keeps 3 Qdrant replicas.",
        "Project Atlas keeps 3 Qdrant replicas.",
    )

    assert match is not None
    assert match.match_type == "exact_normalized_text"


def test_semantic_dedupe_flags_engine_conflict_without_equivalence() -> None:
    assert looks_conflicting_fact(
        "Docs retrieval should use Qdrant vectors.",
        "Postgres owns document vector retrieval.",
    )
    assert not looks_equivalent_fact(
        "Docs retrieval should use Qdrant vectors.",
        "Postgres owns document vector retrieval.",
    )


def test_semantic_dedupe_flags_negated_decision_conflict() -> None:
    assert looks_conflicting_fact(
        "Use Graphiti for temporal facts.",
        "Do not use Graphiti for temporal facts.",
    )


def test_semantic_dedupe_does_not_flag_equivalent_paraphrase_as_conflict() -> None:
    assert not looks_conflicting_fact(
        "Docs retrieval should use Qdrant vectors.",
        "Qdrant owns document vector retrieval.",
    )


def test_semantic_dedupe_rejects_negation_mismatch() -> None:
    assert not looks_equivalent_fact(
        "Use Graphiti for temporal facts.",
        "Do not use Graphiti for temporal facts.",
    )


def test_semantic_terms_normalize_common_memory_aliases() -> None:
    assert "document" in semantic_memory_terms("Docs should be indexed.")
    assert normalize_memory_text("  Graphiti\r\nTemporal   Graph ") == "graphiti temporal graph"
