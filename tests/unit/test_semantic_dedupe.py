from memo_stack_core.application.semantic_dedupe import (
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


def test_semantic_dedupe_rejects_negation_mismatch() -> None:
    assert not looks_equivalent_fact(
        "Use Graphiti for temporal facts.",
        "Do not use Graphiti for temporal facts.",
    )


def test_semantic_terms_normalize_common_memory_aliases() -> None:
    assert "document" in semantic_memory_terms("Docs should be indexed.")
    assert normalize_memory_text("  Graphiti\r\nTemporal   Graph ") == "graphiti temporal graph"
