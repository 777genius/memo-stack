from infinity_context_core.application.context_media_time import (
    enrich_context_item_with_media_time,
    media_time_match_for_source_ref,
    media_time_match_for_source_refs,
    media_time_windows_from_query,
)
from infinity_context_core.application.dto import ContextItem
from infinity_context_core.domain.entities import SourceRef


def test_media_time_query_parses_explicit_timestamps_and_units() -> None:
    windows = media_time_windows_from_query("what happened at 00:42 in the video")
    assert len(windows) == 1
    assert windows[0].start_ms <= 42_000 <= windows[0].end_ms
    assert windows[0].precision == "second"

    ru_windows = media_time_windows_from_query("что было на 42 секунде записи")
    assert len(ru_windows) == 1
    assert ru_windows[0].start_ms <= 42_000 <= ru_windows[0].end_ms

    minute_windows = media_time_windows_from_query("open transcript around minute 7")
    assert len(minute_windows) == 1
    assert minute_windows[0].start_ms <= 420_000 <= minute_windows[0].end_ms
    assert minute_windows[0].precision == "minute"


def test_media_time_query_avoids_plain_clock_time_without_media_cue() -> None:
    assert media_time_windows_from_query("meeting with Alex at 10:30 tomorrow") == ()
    assert media_time_windows_from_query("meeting with Alex at 1:30 tomorrow") == ()
    assert len(media_time_windows_from_query("00:42")) == 1

    windows = media_time_windows_from_query("video timecode 10:30")
    assert len(windows) == 1
    assert windows[0].start_ms <= 630_000 <= windows[0].end_ms


def test_media_time_match_uses_source_ref_time_range_overlap() -> None:
    windows = media_time_windows_from_query("00:42")
    matching = media_time_match_for_source_ref(
        SourceRef(
            source_type="extraction_artifact",
            source_id="artifact_audio",
            chunk_id="segment_42",
            time_start_ms=40_000,
            time_end_ms=45_000,
        ),
        windows,
    )
    decoy = media_time_match_for_source_ref(
        SourceRef(
            source_type="extraction_artifact",
            source_id="artifact_audio",
            chunk_id="segment_5",
            time_start_ms=5_000,
            time_end_ms=9_000,
        ),
        windows,
    )

    assert matching is not None
    assert matching.boost > 0
    assert matching.best_overlap_ms > 0
    assert decoy is None


def test_media_time_match_selects_best_source_ref_overlap() -> None:
    windows = media_time_windows_from_query("video timecode 00:42")

    match = media_time_match_for_source_refs(
        (
            SourceRef(
                source_type="extraction_artifact",
                source_id="artifact_audio",
                chunk_id="segment_1",
                time_start_ms=1_000,
                time_end_ms=2_000,
            ),
            SourceRef(
                source_type="extraction_artifact",
                source_id="artifact_audio",
                chunk_id="segment_42",
                time_start_ms=40_000,
                time_end_ms=45_000,
            ),
        ),
        windows,
    )

    assert match is not None
    assert match.best_overlap_ms > 0


def test_enrich_context_item_with_media_time_adds_boost_and_diagnostics() -> None:
    item = ContextItem(
        item_id="chunk_video_42",
        item_type="chunk",
        text="Project Atlas transcript segment",
        score=0.72,
        source_refs=(
            SourceRef(
                source_type="asset_extraction",
                source_id="video_job",
                chunk_id="segment_42",
                time_start_ms=40_000,
                time_end_ms=45_000,
            ),
        ),
        diagnostics={
            "ranking_reason": "matched via vector_chunks",
            "score_signals": {"base_score": 0.7, "final_score": 0.72},
            "provenance": {"retrieval_sources": ["vector_chunks"]},
        },
    )

    enriched = enrich_context_item_with_media_time(
        item,
        query_text="what did Alex say in the video at 00:42",
    )

    assert enriched.score > item.score
    assert enriched.diagnostics["media_time_query_count"] == 1
    assert enriched.diagnostics["ranking_reason"].endswith("matched requested media timestamp")
    assert enriched.diagnostics["score_signals"]["media_time_matched_window_count"] == 1
    assert enriched.diagnostics["score_signals"]["final_score"] == enriched.score
    assert enriched.diagnostics["provenance"]["media_time_query_count"] == 1


def test_enrich_context_item_with_media_time_ignores_plain_clock_time() -> None:
    item = ContextItem(
        item_id="fact_clock",
        item_type="fact",
        text="Meeting with Alex at 10:30 tomorrow",
        score=0.81,
        source_refs=(
            SourceRef(
                source_type="meeting",
                source_id="meeting_1",
                time_start_ms=628_000,
                time_end_ms=632_000,
            ),
        ),
        diagnostics={"ranking_reason": "matched query"},
    )

    assert (
        enrich_context_item_with_media_time(
            item,
            query_text="meeting with Alex at 10:30 tomorrow",
        )
        is item
    )
