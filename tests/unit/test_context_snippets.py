from infinity_context_core.application.context_snippets import (
    query_focused_snippet,
    source_refs_with_query_snippet,
)
from infinity_context_core.domain.entities import SourceRef


def test_query_focused_snippet_selects_window_around_query_terms() -> None:
    text = (
        "Intro context that is not useful. " * 12
        + "Atlas renewal decision was approved by Alex during the planning call. "
        + "Trailing context that is also not useful. " * 12
    )

    snippet = query_focused_snippet(
        query="Atlas renewal decision Alex",
        text=text,
        window_chars=180,
    )

    assert snippet is not None
    assert "Atlas renewal decision was approved by Alex" in snippet.text
    assert snippet.unique_term_hits == 4
    assert snippet.matched_terms == ("atlas", "renewal", "decision", "alex")
    assert 0 < snippet.char_start < snippet.char_end < len(text)
    assert len(snippet.text) < len(text)


def test_source_refs_with_query_snippet_preserves_location_metadata() -> None:
    source_ref = SourceRef(
        source_type="asset_extraction",
        source_id="artifact_1",
        chunk_id="transcript:1",
        quote_preview="old quote",
        time_start_ms=1200,
        time_end_ms=5400,
    )
    snippet = query_focused_snippet(
        query="Atlas renewal",
        text="Intro. Atlas renewal was approved. Outro.",
    )

    enriched = source_refs_with_query_snippet((source_ref,), snippet)

    assert snippet is not None
    assert enriched[0].quote_preview == snippet.text
    assert enriched[0].time_start_ms == 1200
    assert enriched[0].time_end_ms == 5400
