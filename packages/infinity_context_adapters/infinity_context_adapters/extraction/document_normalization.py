"""Provider-neutral document evidence normalization helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from html import escape
from typing import Any

from infinity_context_core.ports.extraction import (
    ExtractedElement,
    ExtractionArtifactCandidate,
)

_MAX_DOCLING_ELEMENTS = 500
_MAX_DOCLING_ELEMENT_TEXT_CHARS = 4_000
_MIN_TABLE_HTML_CHARS = 1_024
_MAX_TABLE_HTML_CHARS = 100_000


@dataclass(frozen=True)
class NormalizedDocumentEvidence:
    elements: tuple[ExtractedElement, ...]
    artifacts: tuple[ExtractionArtifactCandidate, ...]
    metadata: dict[str, object]


def normalize_docling_document(
    *,
    document: Any,
    markdown: str,
    max_tables: int,
    max_output_chars: int,
    parser_name: str,
) -> NormalizedDocumentEvidence:
    elements = _docling_item_elements(document=document, parser_name=parser_name)
    strategy = "docling_items" if elements else "markdown_blocks"
    if not elements:
        elements = _markdown_block_elements(markdown=markdown, parser_name=parser_name)

    elements, bound_metadata = _bounded_elements(
        elements,
        max_output_chars=max_output_chars,
    )
    artifacts = _table_artifacts(
        document=document,
        elements=elements,
        max_tables=max_tables,
        max_output_chars=max_output_chars,
        parser_name=parser_name,
    )
    metadata = _evidence_metadata(
        elements=elements,
        artifacts=artifacts,
        strategy=strategy,
        markdown_chars=min(len(markdown), max_output_chars),
        bound_metadata=bound_metadata,
    )
    return NormalizedDocumentEvidence(
        elements=tuple(elements),
        artifacts=tuple(artifacts),
        metadata=metadata,
    )


def _docling_item_elements(*, document: Any, parser_name: str) -> list[ExtractedElement]:
    elements: list[ExtractedElement] = []
    for item, level in _iter_document_items(document):
        kind = _item_kind(item)
        text = _item_text(item, document=document, kind=kind)
        if not text and kind != "image":
            continue
        if not text:
            text = _image_placeholder(item)
        elements.append(
            ExtractedElement(
                kind=kind,
                text=text,
                page_number=_item_page_number(item),
                bbox=_item_bbox(item),
                metadata={
                    "source": parser_name,
                    "docling_item_type": _item_type_name(item),
                    "docling_label": _item_label(item),
                    "docling_self_ref": _safe_text(_get_value(item, "self_ref")),
                    "docling_tree_level": level,
                },
            )
        )
    return elements


def _iter_document_items(document: Any) -> list[tuple[Any, int]]:
    iterator = _get_value(document, "iterate_items")
    if callable(iterator):
        try:
            return [
                (item, int(level) if isinstance(level, int) else 0)
                for item, level in iterator(traverse_pictures=True)
            ]
        except TypeError:
            try:
                return [
                    (item, int(level) if isinstance(level, int) else 0)
                    for item, level in iterator()
                ]
            except Exception:
                pass
        except Exception:
            pass

    containers: list[Any] = []
    for attr in ("elements", "items", "texts", "tables", "pictures"):
        value = _get_value(document, attr)
        if value is None:
            continue
        if isinstance(value, dict):
            containers.extend(value.values())
        elif isinstance(value, (list, tuple)):
            containers.extend(value)
    return [(item, 0) for item in containers]


def _markdown_block_elements(*, markdown: str, parser_name: str) -> list[ExtractedElement]:
    blocks = _markdown_blocks(markdown)
    if not blocks:
        return []
    elements: list[ExtractedElement] = []
    for block in blocks:
        kind = "table" if _looks_like_markdown_table(block) else "document_section"
        elements.append(
            ExtractedElement(
                kind=kind,
                text=block,
                metadata={"source": parser_name, "docling_item_type": "markdown_block"},
            )
        )
    return elements


def _markdown_blocks(markdown: str) -> list[str]:
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    return [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]


def _table_artifacts(
    *,
    document: Any,
    elements: list[ExtractedElement],
    max_tables: int,
    max_output_chars: int,
    parser_name: str,
) -> list[ExtractionArtifactCandidate]:
    artifacts: list[ExtractionArtifactCandidate] = []
    table_items = [
        item for item, _level in _iter_document_items(document) if _item_kind(item) == "table"
    ]
    for index, element in enumerate(item for item in elements if item.kind == "table"):
        if len(artifacts) >= max_tables:
            break
        table_item = table_items[index] if index < len(table_items) else None
        raw_html = _table_html(table_item=table_item, document=document, fallback=element.text)
        html_limit = _table_html_limit(max_output_chars)
        html = _bounded_text(raw_html, limit=html_limit)
        if not html.strip():
            continue
        artifacts.append(
            ExtractionArtifactCandidate(
                artifact_type="table_html",
                filename=f"table-{index + 1:03}.html",
                content_type="text/html",
                content=html.encode("utf-8"),
                metadata={
                    "parser": parser_name,
                    "element_kind": element.kind,
                    "table_html_truncated": len(raw_html) > len(html),
                    "table_html_char_limit": html_limit,
                    **(
                        {"page_number": element.page_number}
                        if element.page_number is not None
                        else {}
                    ),
                },
            )
        )
    return artifacts


def _table_html(*, table_item: Any | None, document: Any, fallback: str) -> str:
    if table_item is not None:
        export = _get_value(table_item, "export_to_html")
        if callable(export):
            try:
                return str(export(doc=document, add_caption=True) or "").strip()
            except TypeError:
                try:
                    return str(export(document) or "").strip()
                except Exception:
                    pass
            except Exception:
                pass
    return f"<table><tbody><tr><td><pre>{escape(fallback.strip())}</pre></td></tr></tbody></table>"


def _evidence_metadata(
    *,
    elements: list[ExtractedElement],
    artifacts: list[ExtractionArtifactCandidate],
    strategy: str,
    markdown_chars: int,
    bound_metadata: dict[str, object],
) -> dict[str, object]:
    return {
        "docling_element_strategy": strategy,
        "docling_element_count": len(elements),
        "docling_table_count": sum(1 for item in elements if item.kind == "table"),
        "docling_image_count": sum(1 for item in elements if item.kind == "image"),
        "docling_table_artifact_count": len(artifacts),
        "docling_page_ref_count": sum(1 for item in elements if item.page_number is not None),
        "docling_bbox_ref_count": sum(1 for item in elements if item.bbox is not None),
        "docling_markdown_chars": markdown_chars,
        **bound_metadata,
    }


def _bounded_elements(
    elements: list[ExtractedElement],
    *,
    max_output_chars: int,
) -> tuple[list[ExtractedElement], dict[str, object]]:
    total_candidates = len(elements)
    max_total_chars = max(1, int(max_output_chars))
    bounded: list[ExtractedElement] = []
    text_chars = 0
    text_truncated_count = 0
    for element in elements[:_MAX_DOCLING_ELEMENTS]:
        remaining_chars = max_total_chars - text_chars
        if remaining_chars <= 0:
            break
        text_limit = min(_MAX_DOCLING_ELEMENT_TEXT_CHARS, remaining_chars)
        text = _bounded_text(element.text, limit=text_limit)
        if len(element.text) > len(text):
            text_truncated_count += 1
        text_chars += len(text)
        bounded.append(replace(element, text=text))
    return bounded, {
        "docling_element_count_total": total_candidates,
        "docling_elements_truncated": total_candidates > len(bounded),
        "docling_element_limit": _MAX_DOCLING_ELEMENTS,
        "docling_element_text_char_limit": _MAX_DOCLING_ELEMENT_TEXT_CHARS,
        "docling_element_text_chars": text_chars,
        "docling_element_text_truncated_count": text_truncated_count,
    }


def _bounded_text(text: str, *, limit: int) -> str:
    limit = max(1, int(limit))
    if len(text) <= limit:
        return text
    return text[:limit]


def _table_html_limit(max_output_chars: int) -> int:
    return min(
        max(_MIN_TABLE_HTML_CHARS, int(max_output_chars)),
        _MAX_TABLE_HTML_CHARS,
    )


def _item_kind(item: Any) -> str:
    explicit = _first_text_value(item, ("kind", "label", "type", "name"))
    normalized = explicit.lower().replace(" ", "_") if explicit else _item_type_name(item)
    if "table" in normalized:
        return "table"
    if any(token in normalized for token in ("picture", "image", "figure")):
        return "image"
    if any(token in normalized for token in ("heading", "title", "section")):
        return "section_heading"
    return "document_text"


def _item_text(item: Any, *, document: Any, kind: str) -> str:
    if kind == "table":
        table_markdown = _table_markdown(table_item=item, document=document)
        if table_markdown:
            return table_markdown
    text = _first_text_value(item, ("text", "content", "caption", "markdown"))
    if text:
        return text
    for method_name in ("export_to_markdown", "export_to_text", "to_markdown"):
        method = _get_value(item, method_name)
        if callable(method):
            try:
                value = method()
            except Exception:
                continue
            text = str(value or "").strip()
            if text:
                return text
    return ""


def _table_markdown(*, table_item: Any, document: Any) -> str:
    export = _get_value(table_item, "export_to_markdown")
    if not callable(export):
        return ""
    try:
        return str(export(doc=document) or "").strip()
    except TypeError:
        try:
            return str(export(document) or "").strip()
        except Exception:
            return ""
    except Exception:
        return ""


def _image_placeholder(item: Any) -> str:
    page = _item_page_number(item)
    suffix = f" on page {page}" if page is not None else ""
    return f"Image evidence{suffix}"


def _item_page_number(item: Any) -> int | None:
    direct = _positive_int(_first_value(item, ("page_number", "page_no", "page")))
    if direct is not None:
        return direct
    page_index = _positive_int(_first_value(item, ("page_index",)))
    if page_index is not None:
        return page_index + 1
    provenance = _first_provenance(item)
    if provenance is None:
        return None
    return _positive_int(_first_value(provenance, ("page_number", "page_no", "page")))


def _item_bbox(item: Any) -> tuple[float, float, float, float] | None:
    direct = _bbox_value(_first_value(item, ("bbox", "bounding_box")))
    if direct is not None:
        return direct
    provenance = _first_provenance(item)
    if provenance is None:
        return None
    return _bbox_value(_first_value(provenance, ("bbox", "bounding_box")))


def _first_provenance(item: Any) -> Any | None:
    value = _first_value(item, ("prov", "provenance"))
    if isinstance(value, (list, tuple)) and value:
        return value[0]
    return value


def _bbox_value(value: Any) -> tuple[float, float, float, float] | None:
    if isinstance(value, (list, tuple)) and len(value) == 4:
        numbers = [_float(item) for item in value]
        if all(item is not None for item in numbers):
            return tuple(numbers)  # type: ignore[return-value]
    for attrs in (
        ("l", "t", "r", "b"),
        ("left", "top", "right", "bottom"),
        ("x0", "y0", "x1", "y1"),
    ):
        numbers = [_float(_get_value(value, attr)) for attr in attrs]
        if all(item is not None for item in numbers):
            return tuple(numbers)  # type: ignore[return-value]
    return None


def _first_text_value(item: Any, keys: tuple[str, ...]) -> str | None:
    value = _first_value(item, keys)
    if value is None:
        return None
    text = _safe_text(value)
    return text or None


def _first_value(item: Any, keys: tuple[str, ...]) -> Any | None:
    for key in keys:
        value = _get_value(item, key)
        if value is not None:
            return value
    return None


def _get_value(item: Any, key: str) -> Any | None:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _item_type_name(item: Any) -> str:
    return item.__class__.__name__.lower()


def _item_label(item: Any) -> str | None:
    return _safe_text(_get_value(item, "label"))


def _safe_text(value: Any) -> str | None:
    raw = getattr(value, "value", value)
    text = str(raw).strip()
    return text or None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _looks_like_markdown_table(block: str) -> bool:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    return len(lines) >= 2 and "|" in lines[0] and any(_is_table_separator(line) for line in lines)


def _is_table_separator(line: str) -> bool:
    stripped = line.strip()
    return "|" in stripped and bool(re.fullmatch(r"[:\-\s|]+", stripped))
