"""Markdown-aware document fragment extraction.

The extractor is intentionally deterministic and dependency-free. It upgrades
the document UX without coupling the core to Cognee, Qdrant, or any provider.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from infinity_context_core.application.chunker import TextChunk, chunk_text
from infinity_context_core.domain.entities import MemoryChunkKind

_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_LIST_PATTERN = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+?)\s*$")
_REFERENCE_PATTERN = re.compile(
    r"\b(https?://|ADR[-_ ]?\d+|RFC[-_ ]?\d+|PR\s*#?\d+|issue\s*#?\d+)\b",
    re.IGNORECASE,
)
_CLAIM_PREFIXES = (
    "decision:",
    "claim:",
    "fact:",
    "architecture decision:",
    "constraint:",
)
_PLAN_HEADINGS = {"plan", "implementation", "steps", "next steps", "migration"}
_RISK_HEADINGS = {"risk", "risks", "tradeoffs", "trade-offs", "caveats"}
_REFERENCE_HEADINGS = {"references", "reference", "links", "sources"}
_CLAIM_HEADINGS = {"decision", "decisions", "facts", "claims", "constraints"}
_SHORT_STRUCTURED_DOCUMENT_CHARS = 1_600


@dataclass(frozen=True)
class DocumentFragment:
    text: str
    char_start: int
    char_end: int
    sequence: int
    kind: MemoryChunkKind
    node_kind: str
    heading: str | None = None
    ordinal_in_heading: int | None = None


def fragment_document_text(text: str) -> tuple[DocumentFragment, ...]:
    """Return typed fragments for markdown-ish project documents.

    The fallback remains the existing chunker, so arbitrary long text still
    behaves predictably.
    """

    generic_chunks = chunk_text(text)
    semantic = _semantic_fragments(text)
    if not semantic:
        return tuple(_from_text_chunk(chunk) for chunk in generic_chunks)
    if len(text.strip()) <= _SHORT_STRUCTURED_DOCUMENT_CHARS:
        return _renumbered(tuple(semantic))

    fragments = list(semantic)
    covered_ranges = _covered_ranges(fragments)
    for chunk in generic_chunks:
        if not _range_subsumed(chunk.char_start, chunk.char_end, covered_ranges):
            fragments.append(_from_text_chunk(chunk))

    return _renumbered(
        tuple(sorted(fragments, key=lambda item: (item.char_start, item.char_end)))
    )


def document_fragment_summary(
    fragments: tuple[DocumentFragment, ...],
) -> dict[str, object]:
    return document_fragment_summary_from_nodes(
        (fragment.node_kind, fragment.sequence) for fragment in fragments
    )


def document_fragment_summary_from_nodes(
    nodes: Iterable[tuple[str, int]],
) -> dict[str, object]:
    counts: dict[str, int] = {}
    node_map: dict[str, list[int]] = {}
    total = 0
    for node_kind, sequence in nodes:
        counts[node_kind] = counts.get(node_kind, 0) + 1
        node_map.setdefault(node_kind, []).append(sequence)
        total += 1
    return {
        "fragment_count": total,
        "node_counts": counts,
        "node_map": node_map,
    }


def _semantic_fragments(text: str) -> tuple[DocumentFragment, ...]:
    fragments: list[DocumentFragment] = []
    current_heading: str | None = None
    ordinal_by_heading: dict[str, int] = {}
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        stripped = line.strip()
        line_start = offset
        line_end = offset + len(line)
        offset += len(raw_line)
        if not stripped:
            continue
        heading_match = _HEADING_PATTERN.match(stripped)
        if heading_match:
            current_heading = heading_match.group(2).strip()
            continue
        list_match = _LIST_PATTERN.match(line)
        candidate = list_match.group(1).strip() if list_match else stripped
        node_kind = _node_kind(candidate, current_heading)
        if node_kind == "section_chunk":
            continue
        heading_key = (current_heading or "").casefold()
        ordinal = ordinal_by_heading.get(heading_key, 0)
        ordinal_by_heading[heading_key] = ordinal + 1
        fragments.append(
            DocumentFragment(
                text=candidate,
                char_start=line_start + raw_line.find(candidate),
                char_end=line_end,
                sequence=0,
                kind=_chunk_kind(node_kind),
                node_kind=node_kind,
                heading=current_heading,
                ordinal_in_heading=ordinal,
            )
        )
    return tuple(fragments)


def _node_kind(text: str, heading: str | None) -> str:
    normalized_heading = _normalize_heading(heading)
    normalized_text = text.casefold().strip()
    if normalized_heading in _RISK_HEADINGS or normalized_text.startswith(("risk:", "risk -")):
        return "risk"
    if normalized_heading in _PLAN_HEADINGS:
        return "plan_item"
    if normalized_heading in _REFERENCE_HEADINGS or _REFERENCE_PATTERN.search(text):
        return "reference"
    if normalized_heading in _CLAIM_HEADINGS or normalized_text.startswith(_CLAIM_PREFIXES):
        return "claim"
    return "section_chunk"


def _chunk_kind(node_kind: str) -> MemoryChunkKind:
    return {
        "claim": MemoryChunkKind.DOCUMENT_CLAIM,
        "plan_item": MemoryChunkKind.DOCUMENT_PLAN_ITEM,
        "risk": MemoryChunkKind.DOCUMENT_RISK,
        "reference": MemoryChunkKind.DOCUMENT_REFERENCE,
    }.get(node_kind, MemoryChunkKind.DOCUMENT_SECTION)


def _from_text_chunk(chunk: TextChunk) -> DocumentFragment:
    return DocumentFragment(
        text=chunk.text,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        sequence=chunk.sequence,
        kind=MemoryChunkKind.DOCUMENT_SECTION,
        node_kind="section_chunk",
    )


def _with_sequence(fragment: DocumentFragment, sequence: int) -> DocumentFragment:
    return DocumentFragment(
        text=fragment.text,
        char_start=fragment.char_start,
        char_end=fragment.char_end,
        sequence=sequence,
        kind=fragment.kind,
        node_kind=fragment.node_kind,
        heading=fragment.heading,
        ordinal_in_heading=fragment.ordinal_in_heading,
    )


def _renumbered(fragments: tuple[DocumentFragment, ...]) -> tuple[DocumentFragment, ...]:
    return tuple(
        _with_sequence(fragment, sequence) for sequence, fragment in enumerate(fragments)
    )


def _covered_ranges(fragments: list[DocumentFragment]) -> tuple[tuple[int, int], ...]:
    return tuple((fragment.char_start, fragment.char_end) for fragment in fragments)


def _range_subsumed(start: int, end: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(
        existing_start <= start and end <= existing_end
        for existing_start, existing_end in ranges
    )


def _normalize_heading(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.casefold().strip()
    return normalized.rstrip(":")
