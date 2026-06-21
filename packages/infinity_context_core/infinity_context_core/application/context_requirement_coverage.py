"""Query requirement coverage for prompt-safe memory context."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from infinity_context_core.application.anchor_identity_normalization import canonical_token
from infinity_context_core.application.context_query_intent import QueryAnchorIntent
from infinity_context_core.application.dto import ContextItem
from infinity_context_core.application.safe_payload import safe_metadata_text
from infinity_context_core.domain.entities import MemoryAnchorKind

_MAX_LIST_ITEMS = 12
_MAX_KEY_CHARS = 64

_MODALITY_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "image",
        (
            "image",
            "screenshot",
            "screen shot",
            "picture",
            "photo",
            "ocr",
            "картин",
            "скрин",
            "скриншот",
            "фото",
        ),
    ),
    (
        "audio",
        (
            "audio",
            "voice",
            "speech",
            "transcript",
            "recording",
            "call",
            "аудио",
            "голос",
            "транскрипт",
            "запись",
            "звонок",
            "созвон",
        ),
    ),
    (
        "video",
        (
            "video",
            "keyframe",
            "frame",
            "clip",
            "видео",
            "кадр",
            "ролик",
        ),
    ),
    (
        "document",
        (
            "document",
            "doc",
            "pdf",
            "file",
            "page",
            "документ",
            "файл",
            "страниц",
            "пдф",
        ),
    ),
)

_EVIDENCE_FEATURE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "citation",
        (
            "citation",
            "cite",
            "quote",
            "source",
            "where did",
            "where",
            "цитат",
            "источник",
            "ссылк",
            "где",
        ),
    ),
    (
        "time_range",
        (
            "timestamp",
            "time range",
            "timecode",
            "at ",
            "minute",
            "second",
            "таймкод",
            "время",
            "минута",
            "секунда",
        ),
    ),
    (
        "visual_region",
        (
            "bbox",
            "box",
            "region",
            "ocr",
            "where on screen",
            "область",
            "регион",
            "на скрине",
            "на экране",
        ),
    ),
    (
        "page_or_char",
        (
            "page",
            "paragraph",
            "section",
            "строка",
            "страниц",
            "абзац",
            "раздел",
        ),
    ),
)

_RECENT_EVENT_HINT_RE = re.compile(
    r"\b("
    r"hour ago|hours ago|last week|yesterday|today|"
    r"час назад|часа назад|часов назад|неделю назад|вчера|сегодня"
    r")\b",
    re.IGNORECASE,
)
_EVENT_QUERY_HINT_RE = re.compile(
    r"\b("
    r"call|meeting|sync|chat|message|said|wrote|told|"
    r"звонок|созвон|встреча|чат|переписка|сказал|сказала|написал|написала"
    r")\b",
    re.IGNORECASE,
)
_EXPLICIT_PROJECT_HINT_RE = re.compile(
    r"\b(project|repo|repository|service|проект|репозитор|сервис)\b",
    re.IGNORECASE,
)
_EXPLICIT_PERSON_HINT_RE = re.compile(
    r"\b(person|people|who|with|from|человек|люди|кто|с кем|от кого)\b",
    re.IGNORECASE,
)


def context_requirement_coverage(
    *,
    query: str,
    query_anchor_intent: QueryAnchorIntent,
    items: tuple[ContextItem, ...],
) -> dict[str, object]:
    """Summarize which explicit query requirements are covered by selected context."""

    requested_anchor_kinds = _requested_anchor_kinds(query, query_anchor_intent)
    covered_anchor_kinds = _covered_anchor_kinds(items, query_anchor_intent)
    requested_modalities = _requested_modalities(query)
    covered_modalities = _covered_modalities(items)
    requested_evidence_features = _requested_evidence_features(query)
    covered_evidence_features = _covered_evidence_features(items)

    missing_anchor_kinds = tuple(
        kind for kind in requested_anchor_kinds if kind not in covered_anchor_kinds
    )
    missing_modalities = tuple(
        modality for modality in requested_modalities if modality not in covered_modalities
    )
    missing_features = tuple(
        feature
        for feature in requested_evidence_features
        if feature not in covered_evidence_features
    )
    requested_total = (
        len(requested_anchor_kinds)
        + len(requested_modalities)
        + len(requested_evidence_features)
    )
    covered_total = (
        len(requested_anchor_kinds) - len(missing_anchor_kinds)
        + len(requested_modalities) - len(missing_modalities)
        + len(requested_evidence_features) - len(missing_features)
    )
    missing_total = requested_total - covered_total
    return {
        "schema_version": "context-requirement-coverage-v1",
        "status": _coverage_status(requested_total=requested_total, missing_total=missing_total),
        "requested_total": requested_total,
        "covered_total": covered_total,
        "missing_total": missing_total,
        "coverage_ratio": _ratio(covered_total, requested_total),
        "requested_anchor_kinds": list(requested_anchor_kinds),
        "covered_anchor_kinds": list(covered_anchor_kinds),
        "missing_anchor_kinds": list(missing_anchor_kinds),
        "requested_modalities": list(requested_modalities),
        "covered_modalities": list(covered_modalities),
        "missing_modalities": list(missing_modalities),
        "requested_evidence_features": list(requested_evidence_features),
        "covered_evidence_features": list(covered_evidence_features),
        "missing_evidence_features": list(missing_features),
        "item_count": len(items),
    }


def sanitize_context_requirement_coverage(value: object) -> dict[str, object]:
    """Bound provider-agnostic coverage diagnostics before public exposure."""

    if not isinstance(value, Mapping):
        return {
            "schema_version": "context-requirement-coverage-v1",
            "status": "not_requested",
            "requested_total": 0,
            "covered_total": 0,
            "missing_total": 0,
            "coverage_ratio": 0.0,
            "requested_anchor_kinds": [],
            "covered_anchor_kinds": [],
            "missing_anchor_kinds": [],
            "requested_modalities": [],
            "covered_modalities": [],
            "missing_modalities": [],
            "requested_evidence_features": [],
            "covered_evidence_features": [],
            "missing_evidence_features": [],
            "item_count": 0,
        }
    requested_total = _safe_int(value.get("requested_total"))
    covered_total = (
        min(_safe_int(value.get("covered_total")), requested_total) if requested_total else 0
    )
    missing_total = max(0, requested_total - covered_total) if requested_total else 0
    return {
        "schema_version": "context-requirement-coverage-v1",
        "status": _coverage_status(
            requested_total=requested_total,
            missing_total=missing_total,
        ),
        "requested_total": requested_total,
        "covered_total": covered_total,
        "missing_total": missing_total,
        "coverage_ratio": _ratio(covered_total, requested_total),
        "requested_anchor_kinds": _safe_list(value.get("requested_anchor_kinds")),
        "covered_anchor_kinds": _safe_list(value.get("covered_anchor_kinds")),
        "missing_anchor_kinds": _safe_list(value.get("missing_anchor_kinds")),
        "requested_modalities": _safe_list(value.get("requested_modalities")),
        "covered_modalities": _safe_list(value.get("covered_modalities")),
        "missing_modalities": _safe_list(value.get("missing_modalities")),
        "requested_evidence_features": _safe_list(value.get("requested_evidence_features")),
        "covered_evidence_features": _safe_list(value.get("covered_evidence_features")),
        "missing_evidence_features": _safe_list(value.get("missing_evidence_features")),
        "item_count": _safe_int(value.get("item_count")),
    }


def _requested_anchor_kinds(query: str, intent: QueryAnchorIntent) -> tuple[str, ...]:
    kinds = [
        kind.value
        for kind in MemoryAnchorKind
        if any(
            hint.kind == kind and _anchor_hint_is_explicit(query, hint.kind, hint.reason)
            for hint in intent.hints
        )
    ]
    return _bounded_unique(kinds)


def _anchor_hint_is_explicit(
    query: str,
    kind: MemoryAnchorKind,
    reason: str,
) -> bool:
    if kind == MemoryAnchorKind.EVENT:
        return True
    if _EVENT_QUERY_HINT_RE.search(query) or _RECENT_EVENT_HINT_RE.search(query):
        return True
    safe_reason = _safe_key(reason).replace("_", " ")
    if kind == MemoryAnchorKind.PROJECT:
        return "implicit project context" not in safe_reason or bool(
            _EXPLICIT_PROJECT_HINT_RE.search(query)
        )
    if kind == MemoryAnchorKind.PERSON:
        return "person name" not in safe_reason or bool(_EXPLICIT_PERSON_HINT_RE.search(query))
    return True


def _covered_anchor_kinds(
    items: tuple[ContextItem, ...],
    intent: QueryAnchorIntent,
) -> tuple[str, ...]:
    kinds: list[str] = []
    for item in items:
        diagnostics = _diagnostics(item)
        if item.item_type == "anchor":
            kind = _safe_key(diagnostics.get("anchor_kind") or diagnostics.get("kind"))
            if kind:
                kinds.append(kind)
            else:
                kinds.extend(_anchor_kinds_from_text(item.text))
            continue
        kinds.extend(_anchor_kinds_from_text(item.text))
    item_text_tokens = _item_text_identity_tokens(items)
    for hint in intent.hints:
        if _hint_matches_tokens(hint.label, item_text_tokens) or _hint_matches_tokens(
            hint.canonical_key,
            item_text_tokens,
        ):
            kinds.append(hint.kind.value)
    return _bounded_unique(kinds)


def _anchor_kinds_from_text(text: str) -> tuple[str, ...]:
    lowered = text.casefold()
    kinds: list[str] = []
    for kind in MemoryAnchorKind:
        if f"{kind.value}:" in lowered or f"{kind.value} " in lowered:
            kinds.append(kind.value)
    return tuple(kinds)


def _requested_modalities(query: str) -> tuple[str, ...]:
    lowered = query.casefold()
    return _bounded_unique(
        modality
        for modality, hints in _MODALITY_HINTS
        if any(_modality_hint_matches(lowered, hint) for hint in hints)
    )


def _modality_hint_matches(lowered_query: str, hint: str) -> bool:
    if _is_ascii_word_hint(hint):
        return bool(
            re.search(
                rf"(?<![a-z0-9]){re.escape(hint)}s?(?![a-z0-9])",
                lowered_query,
            )
        )
    return hint in lowered_query


def _is_ascii_word_hint(hint: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+", hint))


def _covered_modalities(items: tuple[ContextItem, ...]) -> tuple[str, ...]:
    modalities: list[str] = []
    for item in items:
        diagnostics = _diagnostics(item)
        modality = _safe_key(diagnostics.get("evidence_modality"))
        if modality:
            modalities.append(modality)
        explicit_modality = modality if modality in {"audio", "document", "image", "video"} else ""
        kind = _safe_key(diagnostics.get("evidence_kind"))
        source_identity_parts = [
            item.item_type,
            kind,
            _safe_key(diagnostics.get("artifact_type")),
            _safe_key(diagnostics.get("retrieval_source")),
        ]
        for ref in item.source_refs:
            source_identity_parts.extend(
                (
                    ref.source_type,
                    ref.source_id,
                    ref.chunk_id or "",
                )
            )
        source_identity = " ".join(source_identity_parts).casefold()
        if explicit_modality != "audio" and (
            "ocr" in kind or any(ref.bbox is not None for ref in item.source_refs)
        ):
            modalities.append("image")
        has_audio_identity = (
            "transcript" in kind
            or "speech" in kind
            or _source_identity_has_any(source_identity, ("audio", "transcript", "speech"))
        )
        has_video_identity = (
            "keyframe" in kind
            or "frame" in kind
            or _source_identity_has_any(
                source_identity,
                ("video", "keyframe", "frame_timeline", "video_frame"),
            )
        )
        if explicit_modality not in {"document", "image", "video"} and (
            has_audio_identity and not has_video_identity
        ):
            modalities.append("audio")
        if explicit_modality not in {"audio", "document", "image"} and has_video_identity:
            modalities.append("video")
        if explicit_modality not in {"audio", "image", "video"} and (
            "document" in kind or "pdf" in kind
        ):
            modalities.append("document")
        for ref in item.source_refs:
            source_type = ref.source_type.casefold()
            if (
                explicit_modality not in {"audio", "image", "video"}
                and source_type in {"document", "document_chunk"}
            ):
                modalities.append("document")
            if (
                explicit_modality not in {"audio", "image", "video"}
                and (
                ref.page_number is not None
                or ref.char_start is not None
                or ref.char_end is not None
                )
            ):
                modalities.append("document")
            if explicit_modality != "audio" and ref.bbox is not None:
                modalities.append("image")
    return _bounded_unique(modalities)


def _source_identity_has_any(source_identity: str, hints: tuple[str, ...]) -> bool:
    return any(hint in source_identity for hint in hints)


def _requested_evidence_features(query: str) -> tuple[str, ...]:
    lowered = query.casefold()
    features = [
        feature
        for feature, hints in _EVIDENCE_FEATURE_HINTS
        if any(hint in lowered for hint in hints)
    ]
    if _RECENT_EVENT_HINT_RE.search(query):
        features.append("time_range")
    return _bounded_unique(features)


def _covered_evidence_features(items: tuple[ContextItem, ...]) -> tuple[str, ...]:
    features: list[str] = []
    for item in items:
        if item.source_refs:
            features.append("citation")
        for ref in item.source_refs:
            if ref.time_start_ms is not None or ref.time_end_ms is not None:
                features.append("time_range")
            if ref.bbox is not None:
                features.append("visual_region")
            if (
                ref.page_number is not None
                or ref.char_start is not None
                or ref.char_end is not None
            ):
                features.append("page_or_char")
    return _bounded_unique(features)


def _coverage_status(*, requested_total: int, missing_total: int) -> str:
    if requested_total <= 0:
        return "not_requested"
    if missing_total <= 0:
        return "satisfied"
    if missing_total < requested_total:
        return "partial"
    return "missing"


def _diagnostics(item: ContextItem) -> Mapping[str, object]:
    diagnostics = item.diagnostics or {}
    provenance = diagnostics.get("provenance")
    if isinstance(provenance, Mapping):
        return {**provenance, **diagnostics}
    return diagnostics


def _item_text_identity_tokens(items: tuple[ContextItem, ...]) -> frozenset[str]:
    tokens: set[str] = set()
    for item in items:
        for raw_token in re.findall(r"[\w.@-]+", item.text.casefold()):
            token = _safe_key(canonical_token(raw_token))
            if token:
                tokens.add(token)
    return frozenset(tokens)


def _hint_matches_tokens(value: str, tokens: frozenset[str]) -> bool:
    hint_tokens = tuple(
        token
        for raw_token in re.findall(r"[\w.@-]+", value.casefold())
        if (token := _safe_key(canonical_token(raw_token)))
    )
    if not hint_tokens:
        return False
    return all(token in tokens for token in hint_tokens)


def _safe_list(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [
        safe
        for item in value[:_MAX_LIST_ITEMS]
        if (safe := _safe_key(item))
    ]


def _bounded_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        safe = _safe_key(value)
        if not safe or safe in seen:
            continue
        seen.add(safe)
        result.append(safe)
        if len(result) >= _MAX_LIST_ITEMS:
            break
    return tuple(result)


def _safe_key(value: object) -> str:
    if value is None:
        return ""
    text = safe_metadata_text(str(value), limit=_MAX_KEY_CHARS).strip().casefold()
    if not text or "[redacted]" in text:
        return ""
    chars = []
    for char in text:
        if char.isalnum() or char in {"_", "-"}:
            chars.append(char)
        elif char.isspace() or char in {"/", ".", ":"}:
            chars.append("_")
    return "".join(chars).strip("_-")[:_MAX_KEY_CHARS]


def _safe_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int | float):
        return max(0, min(10_000, int(value)))
    return 0


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(max(0, min(numerator, denominator)) / denominator, 4)
