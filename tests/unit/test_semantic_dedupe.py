from memo_stack_core.application.semantic_dedupe import (
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


def test_semantic_dedupe_rejects_exclusive_engine_mismatch() -> None:
    assert not looks_equivalent_fact(
        "Docs retrieval should use Qdrant vectors.",
        "Postgres owns document vector retrieval.",
    )


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
