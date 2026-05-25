from memory_core.application.context_packer import ContextPacker
from memory_core.application.dto import ContextItem
from memory_core.domain.entities import SourceRef


def test_context_packer_keeps_profile_sections_and_caps_chunks_per_source() -> None:
    items = tuple(
        ContextItem(
            item_id=f"chunk_same_{index}",
            item_type="chunk",
            text=f"SAME_DOC_MARKER chunk {index}",
            score=1.0 - index * 0.01,
            source_refs=(
                SourceRef(
                    source_type="document",
                    source_id="same-doc",
                    chunk_id=f"chunk_same_{index}",
                ),
            ),
            diagnostics={"profile_id": "profile_default"},
        )
        for index in range(6)
    ) + (
        ContextItem(
            item_id="chunk_other",
            item_type="chunk",
            text="OTHER_DOC_MARKER must still get space.",
            score=0.5,
            source_refs=(
                SourceRef(
                    source_type="document",
                    source_id="other-doc",
                    chunk_id="chunk_other",
                ),
            ),
            diagnostics={"profile_id": "profile_secondary"},
        ),
    )

    result = ContextPacker().pack(
        bundle_id="ctx_test",
        items=items,
        token_budget=2000,
    )

    rendered = result.bundle.rendered_text
    assert "Profile profile_default:" in rendered
    assert "Profile profile_secondary:" in rendered
    assert rendered.count("SAME_DOC_MARKER") == 4
    assert "OTHER_DOC_MARKER" in rendered
    assert result.bundle.diagnostics["dropped_by_source_cap"] == 2
    assert result.bundle.diagnostics["dropped_by_budget"] == 0


def test_context_packer_enforces_rendered_char_cap() -> None:
    items = tuple(
        ContextItem(
            item_id=f"fact_{index}",
            item_type="fact",
            text=f"CHAR_CAP_MARKER fact {index} " + ("details " * 25),
            score=1.0 - index * 0.01,
            source_refs=(SourceRef(source_type="manual", source_id=f"char-cap-{index}"),),
            diagnostics={"profile_id": "profile_default"},
        )
        for index in range(8)
    )

    result = ContextPacker().pack(
        bundle_id="ctx_char_cap",
        items=items,
        token_budget=2000,
        max_rendered_chars=650,
    )

    assert len(result.bundle.rendered_text) <= 650
    assert result.bundle.items
    assert result.bundle.diagnostics["dropped_by_char_cap"] > 0
    assert result.bundle.diagnostics["rendered_chars"] == len(result.bundle.rendered_text)
