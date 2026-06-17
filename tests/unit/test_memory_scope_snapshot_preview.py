from __future__ import annotations

from memo_stack_core.memory_scope_snapshot_preview import build_memory_scope_snapshot_import_preview


def test_memory_scope_snapshot_import_preview_reports_skip_and_supersede() -> None:
    payload = {
        "schema_version": 5,
        "facts": [{"id": "fact_keep"}, {"id": "fact_conflict"}],
        "documents": [{"id": "doc_conflict"}],
        "episodes": [{"id": "episode_keep", "thread_id": "thread_keep"}],
        "chunks": [
            {"id": "chunk_keep", "document_id": "doc_conflict"},
            {"id": "chunk_episode_keep", "episode_id": "episode_keep"},
            {"id": "chunk_orphan", "document_id": "missing_doc"},
        ],
        "captures": [{"id": "capture_keep"}, {"id": "capture_conflict"}],
        "anchors": [
            {"id": "anchor_keep", "kind": "person", "normalized_key": "alex"},
            {"id": "anchor_conflict", "kind": "project", "normalized_key": "atlas"},
        ],
        "context_links": [
            {
                "id": "context_link_keep",
                "source_type": "capture",
                "source_id": "capture_keep",
                "target_type": "anchor",
                "target_id": "anchor_keep",
                "relation_type": "mentions",
            },
            {
                "id": "context_link_anchor_skip",
                "source_type": "capture",
                "source_id": "capture_keep",
                "target_type": "anchor",
                "target_id": "anchor_conflict",
                "relation_type": "mentions",
            },
            {
                "id": "context_link_unsupported",
                "source_type": "asset",
                "source_id": "asset_missing",
                "target_type": "anchor",
                "target_id": "anchor_keep",
                "relation_type": "mentions",
            },
        ],
        "relations": [
            {
                "id": "relation_keep",
                "source_fact_id": "fact_keep",
                "target_fact_id": "fact_conflict",
                "relation_type": "supports",
            }
        ],
        "source_refs": [
            {"fact_id": "fact_keep", "chunk_id": "chunk_keep"},
            {"fact_id": "fact_keep", "chunk_id": "chunk_episode_keep"},
            {"fact_id": "fact_conflict", "chunk_id": "chunk_orphan"},
        ],
    }

    skip_preview = build_memory_scope_snapshot_import_preview(
        payload=payload,
        merge_strategy="skip_existing",
        conflict_ids={"fact_conflict", "doc_conflict", "capture_conflict", "anchor_conflict"},
    )
    supersede_preview = build_memory_scope_snapshot_import_preview(
        payload=payload,
        merge_strategy="supersede_matching_facts",
        conflict_ids={"fact_conflict"},
    )

    assert skip_preview["snapshot_counts"] == {
        "facts": 2,
        "documents": 1,
        "episodes": 1,
        "chunks": 3,
        "captures": 2,
        "anchors": 2,
        "context_links": 3,
        "relations": 1,
        "source_refs": 3,
    }
    assert skip_preview["conflicts"]["facts"] == ["fact_conflict"]
    assert skip_preview["conflicts"]["documents"] == ["doc_conflict"]
    assert skip_preview["conflicts"]["captures"] == ["capture_conflict"]
    assert skip_preview["conflicts"]["anchors"] == ["anchor_conflict"]
    assert skip_preview["would_skip"] == {
        "facts": 1,
        "documents": 1,
        "episodes": 0,
        "chunks": 2,
        "captures": 1,
        "anchors": 1,
        "context_links": 2,
        "relations": 1,
        "source_refs": 2,
    }
    assert skip_preview["would_import"] == {
        "facts": 1,
        "documents": 0,
        "episodes": 1,
        "chunks": 1,
        "captures": 1,
        "anchors": 1,
        "context_links": 1,
        "relations": 0,
        "source_refs": 1,
    }
    assert "some_chunks_will_be_skipped" in skip_preview["warnings"]
    assert "some_relations_will_be_skipped" in skip_preview["warnings"]
    assert "some_context_links_will_be_skipped" in skip_preview["warnings"]
    assert supersede_preview["would_supersede"] == {
        "facts": 1,
        "fact_ids": ["fact_conflict"],
    }
    assert supersede_preview["would_import"]["relations"] == 1


def test_memory_scope_snapshot_import_preview_warns_on_redacted_blocking_conflict() -> None:
    preview = build_memory_scope_snapshot_import_preview(
        payload={"redacted": True, "facts": [{"id": "fact_1"}]},
        merge_strategy="fail_on_conflict",
        conflict_ids={"fact_1"},
    )

    assert preview["conflict_count"] == 1
    assert preview["would_skip"]["facts"] == 0
    assert preview["warnings"] == [
        "redacted_snapshot_cannot_be_applied",
        "conflicts_block_import",
    ]
