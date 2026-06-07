from __future__ import annotations

from pathlib import PurePosixPath

import pytest
from memo_stack_obsidian.domain import SyncMode
from memo_stack_obsidian.layout import LayoutError, ObsidianVaultLayout, safe_scope_segment
from memo_stack_obsidian.note_format import (
    TEXT_END,
    TEXT_START,
    NoteFormatError,
    fact_note_path,
    parse_fact_note,
    render_fact_note,
)


def test_fact_note_render_parse_roundtrip() -> None:
    fact = {
        "id": "fact_123",
        "version": 2,
        "text": "Use Qdrant for document recall.",
        "kind": "architecture_decision",
        "status": "active",
        "category": "retrieval",
    }

    path = fact_note_path(fact["id"])
    note = parse_fact_note(
        path,
        render_fact_note(fact, space_slug="default", profile_external_ref="me"),
    )

    assert note.path == PurePosixPath("Memo Stack/generated/facts/fact_123.md")
    assert note.fact_id == "fact_123"
    assert note.version == 2
    assert note.sync_mode == SyncMode.DIRECT
    assert note.text == "Use Qdrant for document recall."
    assert note.changed_since_export is False


def test_fact_note_detects_managed_text_change() -> None:
    fact = {"id": "fact_123", "version": 2, "text": "Old text."}
    markdown = render_fact_note(fact, space_slug="default", profile_external_ref="me")
    markdown = markdown.replace(
        f"{TEXT_START}\nOld text.\n{TEXT_END}",
        f"{TEXT_START}\nNew text.\n{TEXT_END}",
    )

    note = parse_fact_note(fact_note_path("fact_123"), markdown)

    assert note.text == "New text."
    assert note.changed_since_export is True


def test_fact_note_rejects_missing_managed_block() -> None:
    markdown = "\n".join(
        [
            "---",
            "memo_stack_schema: memo_stack.obsidian.fact.v1",
            "memo_stack_kind: fact",
            "memo_stack_id: fact_123",
            "memo_stack_version: 1",
            "memo_stack_sync_mode: direct",
            "memo_stack_hash: abc",
            "---",
            "# Broken",
            "",
        ]
    )

    with pytest.raises(NoteFormatError, match="Missing managed text start marker"):
        parse_fact_note(PurePosixPath("Memo Stack/generated/facts/fact_123.md"), markdown)


def test_v2_layout_groups_facts_by_space_and_profile() -> None:
    layout = ObsidianVaultLayout.from_values(
        root_folder="AI Memory",
        version="v2",
    )

    path = fact_note_path(
        "fact_123",
        layout=layout,
        space_slug="memo-stack",
        profile_external_ref="belief",
    )

    assert path == PurePosixPath(
        "AI Memory/spaces/memo-stack/profiles/belief/generated/facts/fact_123.md"
    )


def test_scope_segment_slugifies_and_hashes_unsafe_project_names() -> None:
    first = safe_scope_segment("Client Project / Alpha", "space_slug")
    second = safe_scope_segment("Client Project Alpha", "space_slug")

    assert first.startswith("client-project-alpha--")
    assert second.startswith("client-project-alpha--")
    assert first != second
    assert "/" not in first


def test_layout_rejects_unsafe_root_folder() -> None:
    with pytest.raises(LayoutError, match="relative"):
        ObsidianVaultLayout.from_values(root_folder="/tmp/vault", version="v2")

    with pytest.raises(LayoutError, match="parent"):
        ObsidianVaultLayout.from_values(root_folder="../Memo Stack", version="v2")
