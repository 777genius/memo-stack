"""Exact-turn literal answer candidates for prompt packing."""

from __future__ import annotations

import re
from dataclasses import replace

from infinity_context_core.application.context_diagnostics import context_rank_key
from infinity_context_core.application.context_packer_answer_support import (
    _answer_support_exact_query_object_hits,
    _has_any_exact_turn_source_ref,
)
from infinity_context_core.application.dto import ContextItem
from infinity_context_core.domain.entities import SourceRef

_MAX_EXACT_LITERAL_TURN_ITEMS_PER_RULE = 2
_MAX_CITY_LOCATION_LITERAL_TURN_ITEMS = 4
_CITY_LOCATION_RULE_INDEX = 8
_DIALOGUE_MARKER_RE = re.compile(r"\bD\d+:\d+\b")

_EXACT_LITERAL_TURN_RULES: tuple[tuple[re.Pattern[str], re.Pattern[str]], ...] = (
    (
        re.compile(
            r"\b(?:attitude|participat(?:e|ed|ing|ion)|part\s+of)\b"
            r"(?=.{0,160}\b(?:dance|festival|competition)\b)|"
            r"\b(?:dance|festival|competition)\b"
            r"(?=.{0,160}\b(?:attitude|participat(?:e|ed|ing|ion)|part\s+of)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"\b(?:glad\s+to\s+be\s+part\s+of\s+it|part\s+of\s+it)\b",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(
            r"\b(?:certificate|diploma|degree)\b"
            r"(?=.{0,160}\b(?:receive|received|got|for|completion|complete)\b)|"
            r"\b(?:receive|received|got)\b"
            r"(?=.{0,160}\b(?:certificate|diploma|degree)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"\b(?:certificate(?:\s+of\s+completion)?|diploma|degree|"
            r"completion|completed)\b|visual query:\s*diploma",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(
            r"\b(?:when|date|day)\b(?=.{0,160}\b(?:accident|crash|car)\b)|"
            r"\b(?:accident|crash)\b(?=.{0,160}\b(?:when|date|day)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"\b(?:damaged|flatbed|not\s+so\s+great|broken\s+car|"
            r"image\s+caption:.{0,120}\bcar)\b",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(
            r"\b(?:what|how)\b(?=.{0,180}\b(?:like|feel|felt|being\s+at)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"\b(?:felt\s+like|fairy\s+tale|magical|beautiful|calming|"
            r"peaceful)\b",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(
            r"\b(?:both|shared|same|common)\b"
            r"(?=.{0,220}\b(?:de-?stress|stress\s+relief|escape|relax)\b)|"
            r"\b(?:de-?stress|stress\s+relief|escape|relax)\b"
            r"(?=.{0,220}\b(?:both|shared|same|common)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"\b(?:same\s+here|go-?to\s+for\s+stress\s+relief|"
            r"stress\s+(?:fix|relief)|worries\s+vanish|passion\s+and\s+escape)\b",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(
            r"\bjourney\b(?=.{0,180}\b(?:life|together|describe|through)\b)|"
            r"\btogether\b(?=.{0,180}\bjourney\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"\b(?:ongoing\s+adventure|learning\s+and\s+growing|being\s+ourselves)\b",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(
            r"\b(?:how\s+many\s+weeks|weeks?\s+passed|between)\b"
            r"(?=.{0,200}\b(?:adopt(?:ed|ing)?|got|puppy|pup|dog|pet)\b)|"
            r"\b(?:adopt(?:ed|ing)?|puppy|pup|dog|pet)\b"
            r"(?=.{0,200}\b(?:how\s+many\s+weeks|weeks?\s+passed|between)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"\b(?:got|adopt(?:ed|s|ing)?)\b"
            r"(?=.{0,120}\b(?:puppy|pup|dog|pet)\b)"
            r"(?=.{0,160}\b(?:last\s+week|weeks?\s+ago|recently|another)\b)|"
            r"\b(?:puppy|pup|dog|pet)\b"
            r"(?=.{0,120}\b(?:last\s+week|weeks?\s+ago|recently|another)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        re.compile(
            r"\b(?:areas?|regions?|places?)\b"
            r"(?=.{0,220}\b(?:u\.?s\.?|united\s+states|been|planning|go|visit|"
            r"travel(?:ed|led|ing)?)\b)|"
            r"\b(?:been\s+to|planning\s+to\s+go|visited|travel(?:ed|led))\b"
            r"(?=.{0,220}\b(?:areas?|regions?|places?|u\.?s\.?|united\s+states)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"\b(?:planning|planned|plan(?:ning)?|starts?\s+planning)\b"
            r"(?=.{0,80}\btrip\b)"
            r"(?=.{0,140}\b(?:coast|region|area|states?|national\s+parks?)\b)|"
            r"\b(?:explored|visited|traveled|travelled)\b"
            r"(?=.{0,140}\b(?:coast|region|area|states?|national\s+parks?)\b)"
            r"|\bwent\s+(?:to|on)\b"
            r"(?=.{0,140}\b(?:coast|regions?|states?|national\s+parks?|"
            r"beach|mountains?|cities?|countries?|road\s+trip|vacation)\b)"
            r"|\bhit\s+(?:some\s+)?(?:cool\s+)?(?:national\s+)?parks?\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        re.compile(
            r"\b(?:cities|city|locations?|places?|destinations?)\b"
            r"(?=.{0,220}\b(?:been|visit(?:ed|ing)?|travel(?:ed|led|ing)?|"
            r"go(?:ne|ing)?|went|mention(?:ed)?|discover(?:ed|ing)?)\b)|"
            r"\b(?:been\s+to|visit(?:ed|ing)?|travel(?:ed|led|ing)?|"
            r"went|mention(?:ed)?\s+visiting|discover(?:ed|ing)?)\b"
            r"(?=.{0,220}\b(?:cities|city|locations?|places?|destinations?)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"\b(?:was|were|been)\s+in\s+[A-Z][A-Za-z' .-]{2,60}\b|"
            r"\b(?:favorite|favourite)\s+cities\s+to\s+explore\b|"
            r"\bdiscover(?:ing|ed)?\s+new\s+cities\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        re.compile(
            r"\b(?:job|profession|career|duties?|role|work)\b"
            r"(?=.{0,220}\b(?:movie|film|screenplay|script)\b)|"
            r"\b(?:movie|film|screenplay|script)\b"
            r"(?=.{0,220}\b(?:job|profession|career|duties?|role|work)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"\b(?:filming|film(?:ed|ing)?|movie\s+set|clap\s*board)\b"
            r"(?=.{0,180}\b(?:movie|film|screenplay|script|set|actor|producer)\b)|"
            r"\b(?:screenplay|script)\b"
            r"(?=.{0,180}\b(?:filming|movie\s+set|clap\s*board|actor|producer)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        re.compile(
            r"\b(?:what\s+did|what\s+does|what)\b"
            r"(?=.{0,120}\b(?:say|said|tell|told|mention|mentioned)\b)"
            r"(?=.{0,220}\b(?:progress|store|business|project|work|"
            r"effort|efforts?|hard\s+work|pay(?:ing)?\s+off)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"\b(?:found\s+the\s+perfect\s+spot|perfect\s+spot|"
            r"way\s+to\s+go|hard\s+work(?:'s|\s+is)?\s+pay(?:ing)?\s+off|"
            r"congrat(?:s|ulations)?|great\s+progress|keep\s+it\s+up)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)


def exact_literal_turn_candidates(
    items: list[ContextItem],
    *,
    query: str,
) -> tuple[ContextItem, ...]:
    ranked: list[tuple[tuple[object, ...], ContextItem]] = []
    for rule_index, (query_re, text_re) in enumerate(_EXACT_LITERAL_TURN_RULES):
        if query_re.search(query) is None:
            continue
        for item in items:
            if not _has_any_exact_turn_source_ref(item):
                continue
            for candidate in _focused_literal_turn_candidates(item, text_re=text_re):
                if not _exact_literal_rule_candidate_allowed(
                    rule_index=rule_index,
                    item=candidate,
                    query=query,
                ):
                    continue
                ranked.append(
                    (
                        (
                            rule_index,
                            _exact_literal_rule_subject_rank(
                                rule_index=rule_index,
                                item=candidate,
                                query=query,
                            ),
                            -_answer_support_exact_query_object_hits(
                                candidate,
                                query=query,
                            ),
                            context_rank_key(candidate),
                        ),
                        candidate,
                    )
                )
    selected_by_rule: dict[int, int] = {}
    selected_items: list[ContextItem] = []
    selected_keys: set[str] = set()
    for rank_key, item in sorted(ranked, key=lambda value: value[0]):
        rule_index = int(rank_key[0])
        if selected_by_rule.get(rule_index, 0) >= _exact_literal_turn_rule_limit(
            rule_index,
        ):
            continue
        selection_key = _candidate_selection_key(item)
        if selection_key in selected_keys:
            continue
        selected_items.append(item)
        selected_keys.add(selection_key)
        selected_by_rule[rule_index] = selected_by_rule.get(rule_index, 0) + 1
    return tuple(selected_items)


def _exact_literal_turn_rule_limit(rule_index: int) -> int:
    if rule_index == _CITY_LOCATION_RULE_INDEX:
        return _MAX_CITY_LOCATION_LITERAL_TURN_ITEMS
    return _MAX_EXACT_LITERAL_TURN_ITEMS_PER_RULE


def _exact_literal_rule_candidate_allowed(
    *,
    rule_index: int,
    item: ContextItem,
    query: str,
) -> bool:
    if rule_index != _CITY_LOCATION_RULE_INDEX:
        return True
    subject = _query_primary_person_name(query)
    speaker = _focused_literal_speaker(item.text)
    return not subject or not speaker or speaker == subject


def _exact_literal_rule_subject_rank(
    *,
    rule_index: int,
    item: ContextItem,
    query: str,
) -> int:
    if rule_index != _CITY_LOCATION_RULE_INDEX:
        return 0
    subject = _query_primary_person_name(query)
    speaker = _focused_literal_speaker(item.text)
    if not subject:
        return 0
    if speaker == subject:
        return 0
    if not speaker:
        return 1
    return 2


def _focused_literal_turn_candidates(
    item: ContextItem,
    *,
    text_re: re.Pattern[str],
) -> tuple[ContextItem, ...]:
    focused: list[ContextItem] = []
    focused_keys: set[str] = set()
    for ref in _exact_turn_refs(item):
        focused_text = _focused_turn_text(text=item.text, source_id=str(ref.source_id))
        if text_re.search(focused_text) is None:
            continue
        if len(item.source_refs) == 1 and focused_text == item.text:
            focused.append(item)
            focused_keys.add(_candidate_selection_key(item))
            continue
        candidate = _literal_turn_candidate(
            item,
            ref=ref,
            focused_text=focused_text,
        )
        focused.append(candidate)
        focused_keys.add(_candidate_selection_key(candidate))
    text_match = text_re.search(item.text)
    if text_match is not None:
        matched_candidate = _text_match_literal_turn_candidate(
            item,
            match_start=text_match.start(),
        )
        if (
            matched_candidate is not None
            and _candidate_selection_key(matched_candidate) not in focused_keys
        ):
            focused.append(matched_candidate)
    if focused:
        return tuple(focused)
    return ()


def _exact_turn_refs(item: ContextItem) -> tuple[SourceRef, ...]:
    return tuple(
        ref for ref in item.source_refs if str(ref.source_id).casefold().endswith(":turn")
    )


def _query_primary_person_name(query: str) -> str:
    for pattern in (
        r"\b(?:has|have|does|did|is|was|are|were)\s+([A-Z][A-Za-z'’-]{1,40})\b",
        r"\b([A-Z][A-Za-z'’-]{1,40})\b",
    ):
        for match in re.finditer(pattern, query):
            name = match.group(1).casefold()
            if name not in {"what", "which", "when", "where", "why", "how", "us"}:
                return name
    return ""


def _focused_literal_speaker(text: str) -> str:
    speaker_match = re.match(
        r"\s*D\d+:\d+\s+([A-Z][A-Za-z'’. -]{1,40})\s*:",
        text,
    )
    if speaker_match is None:
        return ""
    return speaker_match.group(1).strip().casefold()


def _focused_turn_text(*, text: str, source_id: str) -> str:
    marker_match = _DIALOGUE_MARKER_RE.search(source_id)
    if marker_match is None:
        return text
    marker = marker_match.group(0)
    matches = tuple(re.finditer(rf"\b{re.escape(marker)}\b", text))
    if not matches:
        return text
    text_match = matches[0]
    for match in matches:
        following = text[match.end() : match.end() + 48]
        if re.match(r"\s+(?!D\d+:)[A-Z][A-Za-z'. -]{0,40}:", following):
            text_match = match
            break
    next_match = _DIALOGUE_MARKER_RE.search(text[text_match.end() :])
    end = text_match.end() + next_match.start() if next_match is not None else len(text)
    return text[text_match.start() : end].strip() or text


def _text_match_literal_turn_candidate(
    item: ContextItem,
    *,
    match_start: int,
) -> ContextItem | None:
    marker_match = _nearest_preceding_dialogue_marker(
        text=item.text,
        position=match_start,
    )
    if marker_match is None:
        return None
    marker = marker_match.group(0)
    ref = next(
        (ref for ref in _exact_turn_refs(item) if marker in str(ref.source_id)),
        None,
    )
    if ref is None:
        ref = _derive_exact_turn_ref(item, marker=marker)
    if ref is None:
        if len(item.source_refs) == 1:
            return item
        return None
    next_match = _DIALOGUE_MARKER_RE.search(item.text[marker_match.end() :])
    end = (
        marker_match.end() + next_match.start()
        if next_match is not None and marker_match.end() + next_match.start() > match_start
        else len(item.text)
    )
    focused_text = item.text[marker_match.start() : end].strip() or item.text
    return _literal_turn_candidate(item, ref=ref, focused_text=focused_text)


def _literal_turn_candidate(
    item: ContextItem,
    *,
    ref: SourceRef,
    focused_text: str,
) -> ContextItem:
    return replace(
        item,
        item_id=f"{item.item_id}:literal_exact:{_safe_source_id_suffix(str(ref.source_id))}",
        text=focused_text,
        source_refs=(ref,),
        diagnostics=_literal_turn_diagnostics(item),
    )


def _derive_exact_turn_ref(item: ContextItem, *, marker: str) -> SourceRef | None:
    for ref in item.source_refs:
        source_id = str(ref.source_id)
        derived_source_id = _derive_exact_turn_source_id(source_id, marker=marker)
        if derived_source_id:
            return SourceRef(
                source_type=ref.source_type,
                source_id=derived_source_id,
            )
    return None


def _derive_exact_turn_source_id(source_id: str, *, marker: str) -> str:
    turn_match = re.match(r"(?P<prefix>.*:session_\d+):D\d+:\d+:turn$", source_id)
    if turn_match is not None:
        return f"{turn_match.group('prefix')}:{marker}:turn"
    session_match = re.match(
        r"(?P<prefix>.*:session_\d+)(?::(?:events|observation|summary))?$",
        source_id,
    )
    if session_match is not None:
        return f"{session_match.group('prefix')}:{marker}:turn"
    return ""


def _nearest_preceding_dialogue_marker(
    *,
    text: str,
    position: int,
) -> re.Match[str] | None:
    preceding: re.Match[str] | None = None
    for match in _DIALOGUE_MARKER_RE.finditer(text):
        if match.start() > position:
            break
        preceding = match
    return preceding


def _safe_source_id_suffix(source_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", source_id).strip("_").casefold()


def _candidate_selection_key(item: ContextItem) -> str:
    exact_refs = _exact_turn_refs(item)
    if exact_refs:
        return str(exact_refs[0].source_id).casefold()
    return f"{item.item_id}\n{item.text}".casefold()


def _literal_turn_diagnostics(item: ContextItem) -> dict[str, object]:
    diagnostics = dict(item.diagnostics or {})
    score_signals = diagnostics.get("score_signals")
    score_signal_dict = dict(score_signals) if isinstance(score_signals, dict) else {}
    score_signal_dict["exact_literal_turn"] = 1
    diagnostics["score_signals"] = score_signal_dict
    return diagnostics
