from memo_stack_core.application.document_fragments import (
    document_fragment_summary,
    fragment_document_text,
)
from memo_stack_core.domain.entities import MemoryChunkKind


def test_fragment_document_text_extracts_typed_markdown_nodes() -> None:
    fragments = fragment_document_text(
        "\n".join(
            [
                "# ADR-0007",
                "## Decision",
                "- Use FastAPI for the public API.",
                "## Risks",
                "- Do not run Graphiti projections in the request path.",
                "## Plan",
                "1. Keep canonical facts in Postgres.",
                "## References",
                "- ADR-0004",
            ]
        )
    )

    assert [fragment.node_kind for fragment in fragments] == [
        "claim",
        "risk",
        "plan_item",
        "reference",
    ]
    assert [fragment.sequence for fragment in fragments] == [0, 1, 2, 3]
    assert [fragment.kind for fragment in fragments] == [
        MemoryChunkKind.DOCUMENT_CLAIM,
        MemoryChunkKind.DOCUMENT_RISK,
        MemoryChunkKind.DOCUMENT_PLAN_ITEM,
        MemoryChunkKind.DOCUMENT_REFERENCE,
    ]
    assert fragments[0].heading == "Decision"
    assert fragments[0].ordinal_in_heading == 0
    assert fragments[0].text == "Use FastAPI for the public API."


def test_fragment_document_text_falls_back_to_section_chunks_for_plain_text() -> None:
    fragments = fragment_document_text("Plain architecture note without markdown semantics.")

    assert len(fragments) == 1
    assert fragments[0].node_kind == "section_chunk"
    assert fragments[0].kind == MemoryChunkKind.DOCUMENT_SECTION


def test_document_fragment_summary_groups_sequences_by_node_kind() -> None:
    fragments = fragment_document_text(
        "\n".join(
            [
                "## Facts",
                "- Canonical memory lives in Postgres.",
                "- Qdrant is a derived projection.",
                "## Risks",
                "- Do not expose pending suggestions as facts.",
            ]
        )
    )

    summary = document_fragment_summary(fragments)

    assert summary == {
        "fragment_count": 3,
        "node_counts": {"claim": 2, "risk": 1},
        "node_map": {"claim": [0, 1], "risk": [2]},
    }
