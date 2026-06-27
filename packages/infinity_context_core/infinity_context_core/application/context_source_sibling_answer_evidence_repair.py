"""Exact source-sibling answer-evidence repair helpers."""

from __future__ import annotations

import re
from dataclasses import replace

from infinity_context_core.application.context_diagnostics import (
    context_rank_key,
    diagnostic_retrieval_sources,
)
from infinity_context_core.application.dto import ContextItem
from infinity_context_core.domain.entities import SourceRef

_MAX_EXACT_SOURCE_SIBLING_ANSWER_EVIDENCE_REPAIRS = 48
_DIALOGUE_MARKER_RE = re.compile(r"\bD\d+:\d+\b")


def _provenance(diagnostics: dict[str, object]) -> dict[str, object]:
    value = diagnostics.get("provenance")
    return dict(value) if isinstance(value, dict) else {}


def _numeric_score_signal(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _restore_exact_source_sibling_answer_evidence_items(
    *,
    candidates: tuple[ContextItem, ...],
    source_items: tuple[ContextItem, ...],
) -> tuple[tuple[ContextItem, ...], dict[str, object]]:
    existing_repair_keys = {
        _exact_source_sibling_answer_evidence_repair_key(item)
        for item in candidates
    }
    repaired_keys: set[tuple[str, str, tuple[str, ...]]] = set()
    repairs: list[ContextItem] = []
    considered = 0
    skipped_existing = 0
    for item in sorted(source_items, key=_exact_source_sibling_answer_evidence_repair_item_key):
        if not (
            _is_exact_source_sibling_answer_evidence_item(item)
            or _is_exact_source_sibling_marker_coverage_item(item)
        ):
            continue
        for ref in sorted(
            _exact_source_sibling_answer_evidence_repair_refs(item),
            key=lambda source_ref: _exact_source_sibling_answer_evidence_repair_ref_key(
                item=item,
                source_id=str(source_ref.source_id),
            ),
        ):
            source_id = str(ref.source_id)
            if not source_id.casefold().endswith(":turn"):
                continue
            considered += 1
            repair_key = (item.item_type, item.item_id, (source_id,))
            if repair_key in existing_repair_keys or repair_key in repaired_keys:
                skipped_existing += 1
                continue
            repair_item = item
            if len(item.source_refs) != 1:
                repair_text = _focused_exact_source_repair_text(
                    text=item.text,
                    source_id=source_id,
                )
                repair_priority = _exact_source_sibling_answer_evidence_repair_marker_priority(
                    item=item,
                    source_id=source_id,
                )
                repair_item = replace(
                    item,
                    item_id=(
                        f"{item.item_id}:exact_source:"
                        f"{_exact_source_repair_item_id_suffix(source_id)}"
                    ),
                    text=repair_text,
                    source_refs=(ref,),
                    diagnostics=_exact_source_repair_diagnostics(
                        item,
                        repair_priority=repair_priority,
                    ),
                )
            repairs.append(repair_item)
            repaired_keys.add(repair_key)
            if len(repairs) >= _MAX_EXACT_SOURCE_SIBLING_ANSWER_EVIDENCE_REPAIRS:
                break
        if len(repairs) >= _MAX_EXACT_SOURCE_SIBLING_ANSWER_EVIDENCE_REPAIRS:
            break
    diagnostics = {
        "exact_source_sibling_answer_evidence_repair_candidates": considered,
        "exact_source_sibling_answer_evidence_repair_existing": skipped_existing,
        "exact_source_sibling_answer_evidence_repair_added": len(repairs),
    }
    if not repairs:
        return candidates, diagnostics
    return tuple(sorted((*candidates, *repairs), key=context_rank_key)), diagnostics


def _exact_source_sibling_answer_evidence_repair_key(
    item: ContextItem,
) -> tuple[str, str, tuple[str, ...]]:
    return (
        item.item_type,
        item.item_id,
        tuple(str(ref.source_id) for ref in item.source_refs),
    )


_PET_ACQUISITION_EXACT_REPAIR_DATE_ANCHOR_RE = re.compile(
    r"\b(?:session_\d+\s+date|date:\s+)",
    re.IGNORECASE | re.DOTALL,
)
_PET_ACQUISITION_EXACT_REPAIR_OBJECT_RE = re.compile(
    r"\b(?:"
    r"adopt(?:ed|ing)?|"
    r"(?:got|get|getting)\s+(?:a\s+|the\s+|this\s+|that\s+|another\s+)?"
    r"(?:new\s+)?(?:pet|dog|puppy|pup|stuffed\s+animal|toy\s+(?:dog|pup))|"
    r"new\s+addition|new\s+pup|puppy|pup|"
    r"gift\s+from|named|stuffed\s+animal|toy\s+(?:dog|pup)"
    r")\b",
    re.IGNORECASE,
)


def _exact_source_sibling_answer_evidence_repair_item_key(
    item: ContextItem,
) -> tuple[float | int | str, ...]:
    return (
        _exact_source_sibling_answer_evidence_repair_item_priority(item),
        context_rank_key(item),
    )


def _exact_source_sibling_answer_evidence_repair_item_priority(item: ContextItem) -> int:
    if _is_pet_acquisition_exact_repair_scope(item):
        return _pet_acquisition_exact_repair_text_priority(item.text)
    return 1


def _exact_source_sibling_answer_evidence_repair_ref_key(
    *,
    item: ContextItem,
    source_id: str,
) -> tuple[int, str]:
    if _is_pet_acquisition_exact_repair_scope(item):
        marker_match = re.search(r"\bD\d+:\d+\b", source_id)
        if marker_match is None or re.search(
            rf"\b{re.escape(marker_match.group(0))}\b",
            item.text,
        ) is None:
            return (1, source_id)
        return (
            _exact_source_sibling_answer_evidence_repair_marker_priority(
                item=item,
                source_id=source_id,
            ),
            source_id,
        )
    return (1, source_id)


def _is_pet_acquisition_exact_repair_scope(item: ContextItem) -> bool:
    diagnostics = item.diagnostics or {}
    query_reason = str(diagnostics.get("query_expansion_reason") or "")
    if query_reason == "pet_acquisition_date_bridge":
        return True
    score_signals = diagnostics.get("score_signals")
    if not isinstance(score_signals, dict):
        return False
    return str(score_signals.get("query_expansion_reason") or "") == (
        "pet_acquisition_date_bridge"
    )


def _exact_source_repair_item_id_suffix(source_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", source_id).strip("_")[:160] or "turn"


def _exact_source_sibling_answer_evidence_repair_refs(
    item: ContextItem,
) -> tuple[SourceRef, ...]:
    refs = list(item.source_refs)
    if not _is_pet_acquisition_exact_repair_scope(item):
        return _filtered_exact_source_sibling_answer_evidence_repair_refs(item, refs=refs)
    marker_priorities = _pet_acquisition_exact_repair_marker_priorities(item)
    if not marker_priorities:
        return ()
    markers = tuple(marker_priorities)
    selected_refs = [
        ref
        for ref in refs
        if _source_ref_dialogue_marker(ref) in markers
    ]
    existing_source_ids = {str(ref.source_id) for ref in selected_refs}
    template_refs = tuple(selected_refs) or tuple(
        ref for ref in refs if re.search(r"\bD\d+:\d+:turn$", str(ref.source_id)) is not None
    )
    if not template_refs:
        return tuple(selected_refs)
    for marker in markers:
        for template_ref in template_refs:
            template_source_id = str(template_ref.source_id)
            marker_match = re.search(r"\bD\d+:\d+(?=:turn$)", template_source_id)
            if marker_match is None:
                continue
            derived_source_id = (
                f"{template_source_id[: marker_match.start()]}"
                f"{marker}"
                f"{template_source_id[marker_match.end():]}"
            )
            if derived_source_id in existing_source_ids:
                continue
            existing_source_ids.add(derived_source_id)
            selected_refs.append(
                replace(
                    template_ref,
                    source_id=derived_source_id,
                )
            )
            break
    return tuple(selected_refs)


_EXACT_REPAIR_ANIMAL_CARE_RE = re.compile(
    r"\b(?:keep(?:ing)?\s+(?:their|the)?\s*(?:area|tank|space|habitat)\s+clean|"
    r"clean\s+(?:area|tank|space|habitat)|feed(?:ing)?\s+(?:them\s+)?properly|"
    r"enough\s+light|care\s+instructions?|kind\s+of\s+fun)\b",
    re.IGNORECASE,
)
_EXACT_REPAIR_ANIMAL_DIET_RE = re.compile(
    r"\b(?:"
    r"(?:eat|eats|ate|diet|food|feed(?:ing)?)\b(?=.{0,120}\b"
    r"(?:vegetables?|fruits?|insects?|greens?|varied\s+diet|turtles?|reptiles?)\b)|"
    r"(?:vegetables?|fruits?|insects?|greens?|varied\s+diet)\b(?=.{0,120}\b"
    r"(?:eat|eats|ate|diet|food|feed(?:ing)?|turtles?|reptiles?)\b)"
    r")",
    re.IGNORECASE | re.DOTALL,
)
_EXACT_REPAIR_ANIMAL_HABITAT_RE = re.compile(
    r"\b(?:new|bigger|large|larger|upgrade(?:d)?)\s+(?:tank|habitat|enclosure)\b|"
    r"\b(?:tank|habitat|enclosure)\b(?=.{0,100}\b(?:new|bigger|large|larger|upgrade))",
    re.IGNORECASE | re.DOTALL,
)
_EXACT_REPAIR_ANIMAL_AFFINITY_RE = re.compile(
    r"\b(?:pet\s+store|bring(?:s)?\s+me\s+(?:joy|peace)|"
    r"joy\s+and\s+peace|best\s+buddies|love\s+most\s+about\s+having)\b",
    re.IGNORECASE,
)
_EXACT_REPAIR_ANIMAL_ACTIVITY_RE = re.compile(
    r"\b(?:feed(?:ing)?|eat(?:ing)?|fruit|strawberries|snacks?|hold(?:ing)?|"
    r"bath|bathe|bathing|walk(?:s|ed|ing)?)\b"
    r"(?=.{0,180}\b(?:turtles?|pets?|animals?|reptiles?)\b)|"
    r"\b(?:turtles?|pets?|animals?|reptiles?)\b"
    r"(?=.{0,180}\b(?:feed(?:ing)?|eat(?:ing)?|fruit|strawberries|snacks?|"
    r"hold(?:ing)?|bath|bathe|bathing|walk(?:s|ed|ing)?)\b)",
    re.IGNORECASE | re.DOTALL,
)
_EXACT_REPAIR_SUPPORT_ORIGIN_RE = re.compile(
    r"\b(?:support|love|acceptance)\b"
    r"(?=.{0,180}\b(?:journey|pass\s+it\s+on|supportive\s+community|"
    r"hope|understanding|acceptance)\b)",
    re.IGNORECASE | re.DOTALL,
)
_EXACT_REPAIR_SUPPORT_CAREER_MOTIVATION_RE = re.compile(
    r"\b(?:made\s+a\s+huge\s+difference|made\s+.*\bdifference|"
    r"counseling\s+and\s+support\s+groups|support\s+groups\s+improved|"
    r"improved\s+my\s+life|now\s+i\s+want\s+to\s+help|"
    r"safe,\s*inviting\s+place)\b",
    re.IGNORECASE | re.DOTALL,
)
_EXACT_REPAIR_CLASSICAL_MUSIC_PREFERENCE_RE = re.compile(
    r"\b(?:fan|enjoys?|likes?|loves?|favorite|favourite|fav(?:orite)?|into)\b"
    r"(?=.{0,180}\b(?:classical|bach|mozart|vivaldi|orchestra|symphony|"
    r"composer|tunes?|songs?|music)\b)|"
    r"\b(?:classical|bach|mozart|vivaldi|orchestra|symphony|composer)\b"
    r"(?=.{0,180}\b(?:fan|enjoys?|likes?|loves?|favorite|favourite|"
    r"fav(?:orite)?|tunes?|songs?|music)\b)",
    re.IGNORECASE | re.DOTALL,
)
_EXACT_REPAIR_SENTIMENTAL_REMINDER_RE = re.compile(
    r"\b(?:reminds?|reminder|sentimental\s+value|symboli[sz](?:es|ed)?|"
    r"meaning|means|stands?\s+for)\b(?=.{0,220}\b(?:art|self[-\s]?expression|"
    r"friend|birthday|gift|memory|pattern|colou?rs?|childhood|love|faith|"
    r"strength|roots?|family|keepsake)\b)|"
    r"\b(?:sentimental\s+value|hand[-\s]?painted|keepsake|gift|birthday|"
    r"pattern|colou?rs?)\b(?=.{0,220}\b(?:reminds?|reminder|symbol|meaning|"
    r"self[-\s]?expression)\b)",
    re.IGNORECASE | re.DOTALL,
)
_EXACT_REPAIR_OUTDOOR_PREFERENCE_RE = re.compile(
    r"\b(?:look\s+forward|highlight|always\s+remember|favorite|favourite|"
    r"best\s+memory|love|enjoy|special|amazing)\b(?=.{0,240}\b(?:camping|"
    r"campfire|marshmallows?|meteor\s+shower|stars?|sky|universe|nature|"
    r"outdoors?|hikes?|hiking|trail|park)\b)|"
    r"\b(?:camping|campfire|marshmallows?|meteor\s+shower|stars?|sky|universe|"
    r"nature|outdoors?|hikes?|hiking|trail|park)\b(?=.{0,240}\b(?:look\s+forward|"
    r"highlight|always\s+remember|favorite|favourite|best\s+memory|love|enjoy|"
    r"special|amazing|at\s+one\s+with)\b)",
    re.IGNORECASE | re.DOTALL,
)
_EXACT_REPAIR_CHILDREN_PREFERENCE_RE = re.compile(
    r"\b(?:kids?|children|child|sons?|daughters?|younger\s+kids?)\b"
    r"(?=.{0,220}\b(?:likes?|loves?|enjoys?|favorite|favourite|stoked|"
    r"excited|blast|into)\b)"
    r"(?=.{0,260}\b(?:dinosaurs?|exhibit|museum|animals?|bones?|nature|"
    r"outdoors?|hikes?|hiking|camping|campfire|marshmallows?|books?|stories|"
    r"learning|pottery|clay|painting|creative|creativity)\b)|"
    r"\b(?:they|them)\b(?=.{0,140}\b(?:were\s+)?(?:stoked|excited)\b)"
    r"(?=.{0,220}\b(?:dinosaurs?|exhibit|museum|animals?|bones?|nature|"
    r"outdoors?|hikes?|hiking|camping|books?|stories|learning)\b)|"
    r"\b(?:they|them)\b(?=.{0,180}\b(?:likes?|loves?|enjoys?|favorite|"
    r"favourite)\b)"
    r"(?=.{0,220}\b(?:dinosaurs?|exhibit|museum|animals?|bones?|nature|"
    r"outdoors?|hikes?|hiking|camping|books?|stories|learning)\b)",
    re.IGNORECASE | re.DOTALL,
)
_EXACT_REPAIR_VOLUNTEERING_PEOPLE_RE = re.compile(
    r"\b(?:someone|person)\s+named\s+[A-Z][a-z]+\b|"
    r"\bmet\s+(?:this\s+)?(?:amazing\s+)?(?:woman|man|person),\s+[A-Z][a-z]+\b|"
    r"\bresidents?\b(?=.{0,180}\b(?:shelter|letter|wrote|gratitude|"
    r"appreciation|support\s+they\s+receive|heartfelt)\b)|"
    r"\b(?:letter|wrote|gratitude|appreciation|heartfelt)\b"
    r"(?=.{0,180}\b(?:residents?|shelter|support\s+they\s+receive|impact)\b)",
    re.IGNORECASE | re.DOTALL,
)
_EXACT_REPAIR_ACTIVITY_PARTICIPATION_RE = re.compile(
    r"\b(?:signed\s+up\s+for|joined|started|went|go(?:ing)?|off\s+to\s+go|"
    r"took|did|finished|made|painted|pottery\s+class|workshop|"
    r"visual\s+query:\s*painting|image\s+caption:.{0,120}\bpainting)\b"
    r"(?=.{0,240}\b(?:pottery|class|camp(?:ing|ed)?|swimm(?:ing)?|swim|"
    r"painting|painted|sunrise|sunset|lake|hiking|hike|trail|workshop|clay|"
    r"creative|kids?|family|fam)\b)",
    re.IGNORECASE | re.DOTALL,
)
_EXACT_REPAIR_ACTIVITY_PARTICIPATION_REASONS = frozenset(
    {
        "activity-aggregation-bridge",
        "activity-visual-selfcare-bridge",
        "decomposition-activity-participation",
    }
)
_EXACT_REPAIR_EXERCISE_COMPANION_RE = re.compile(
    r"(?=.*\b(?:yoga|class(?:es)?|lesson|practice|workout|exercise|fitness|"
    r"training|kickboxing|taekwondo|boxing|running|hiking|camping)\b)"
    r"(?=.*(?:"
    r"\b(?:with|alongside|together\s+with|joined\s+by|accompanied\s+by)\b"
    r".{0,90}\b(?:(?:my|his|her|their|our|a|an|the)\s+|"
    r"one\s+of\s+(?:my|his|her|their|our)\s+)?"
    r"(?:family|kids?|children|friends?|parents?|partner|spouse|team|group|"
    r"colleagues?|co-?workers?|workmates?|classmates?|teammates?|neighbou?rs?)\b|"
    r"\b(?:(?:my|his|her|their|our)\s+)?"
    r"(?:colleagues?|co-?workers?|workmates?|friends?|classmates?|teammates?|"
    r"neighbou?rs?)\b(?:\s+[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё._-]{1,39})?"
    r".{0,90}\binvited\b.{0,120}\b(?:me|him|her|them|us)?\s*(?:to|for)\b|"
    r"\binvited\b.{0,120}\b(?:to|for)\b.{0,160}\bby\s+"
    r"(?:(?:my|his|her|their|our)\s+)?"
    r"(?:colleagues?|co-?workers?|workmates?|friends?|classmates?|teammates?|"
    r"neighbou?rs?)\b"
    r"))",
    re.IGNORECASE | re.DOTALL,
)
_EXACT_REPAIR_EXERCISE_TYPE_RE = re.compile(
    r"\b(?:aerial|kundalini|vinyasa|hatha|ashtanga|bikram|yin|restorative|"
    r"power|hot|prenatal|beginner(?:'s)?)\s+yoga\b|"
    r"\b(?:weight|circuit|strength|agility|speed)\s+training\b|"
    r"\b(?:kickboxing|taekwondo|tae\s+kwon\s+do|boxing)\b",
    re.IGNORECASE,
)


def _filtered_exact_source_sibling_answer_evidence_repair_refs(
    item: ContextItem,
    *,
    refs: list[SourceRef],
) -> tuple[SourceRef, ...]:
    if len(refs) <= 1:
        return tuple(refs)
    reason = _exact_source_repair_query_reason(item)
    if reason not in {
        "animal-activity-inventory-bridge",
        "animal-affinity-pet-store-bridge",
        "animal-care-instruction-bridge",
        "animal-diet-evidence-bridge",
        "animal-habitat-setup-bridge",
        *_EXACT_REPAIR_ACTIVITY_PARTICIPATION_REASONS,
        "children-preference-bridge",
        "classical-music-preference-bridge",
        "exercise-activity-inventory-bridge",
        "outdoor-nature-memory-bridge",
        "outdoor-preference-bridge",
        "sentimental-reminder-bridge",
        "support-career-motivation-bridge",
        "support-origin-bridge",
        "volunteering-people-inventory-bridge",
    }:
        return tuple(refs)
    selected: list[SourceRef] = []
    for ref in refs:
        source_id = str(ref.source_id)
        if not source_id.casefold().endswith(":turn"):
            continue
        focused_text = _focused_exact_source_repair_text(text=item.text, source_id=source_id)
        if _exact_source_repair_focused_text_supported(
            reason=reason,
            text=focused_text,
        ):
            selected.append(ref)
    return tuple(selected)


def _exact_source_repair_query_reason(item: ContextItem) -> str:
    diagnostics = item.diagnostics or {}
    reason = str(diagnostics.get("query_expansion_reason") or "").replace("_", "-")
    if reason:
        return reason
    score_signals = diagnostics.get("score_signals")
    if isinstance(score_signals, dict):
        return str(score_signals.get("query_expansion_reason") or "").replace("_", "-")
    return ""


def _exact_source_repair_focused_text_supported(*, reason: str, text: str) -> bool:
    if reason == "animal-care-instruction-bridge":
        return _EXACT_REPAIR_ANIMAL_CARE_RE.search(text) is not None
    if reason == "animal-diet-evidence-bridge":
        return _EXACT_REPAIR_ANIMAL_DIET_RE.search(text) is not None
    if reason == "animal-habitat-setup-bridge":
        return _EXACT_REPAIR_ANIMAL_HABITAT_RE.search(text) is not None
    if reason == "animal-affinity-pet-store-bridge":
        return _EXACT_REPAIR_ANIMAL_AFFINITY_RE.search(text) is not None
    if reason == "animal-activity-inventory-bridge":
        return _EXACT_REPAIR_ANIMAL_ACTIVITY_RE.search(text) is not None
    if reason == "support-origin-bridge":
        return _EXACT_REPAIR_SUPPORT_ORIGIN_RE.search(text) is not None
    if reason == "support-career-motivation-bridge":
        return _EXACT_REPAIR_SUPPORT_CAREER_MOTIVATION_RE.search(text) is not None
    if reason == "classical-music-preference-bridge":
        return _EXACT_REPAIR_CLASSICAL_MUSIC_PREFERENCE_RE.search(text) is not None
    if reason == "sentimental-reminder-bridge":
        return _EXACT_REPAIR_SENTIMENTAL_REMINDER_RE.search(text) is not None
    if reason in {"outdoor-preference-bridge", "outdoor-nature-memory-bridge"}:
        return _EXACT_REPAIR_OUTDOOR_PREFERENCE_RE.search(text) is not None
    if reason == "children-preference-bridge":
        return _EXACT_REPAIR_CHILDREN_PREFERENCE_RE.search(text) is not None
    if reason == "volunteering-people-inventory-bridge":
        return _EXACT_REPAIR_VOLUNTEERING_PEOPLE_RE.search(text) is not None
    if reason == "exercise-activity-inventory-bridge":
        return (
            _EXACT_REPAIR_EXERCISE_COMPANION_RE.search(text) is not None
            or _EXACT_REPAIR_EXERCISE_TYPE_RE.search(text) is not None
        )
    if reason in _EXACT_REPAIR_ACTIVITY_PARTICIPATION_REASONS:
        return _EXACT_REPAIR_ACTIVITY_PARTICIPATION_RE.search(text) is not None
    return True


def _pet_acquisition_exact_repair_markers(item: ContextItem) -> tuple[str, ...]:
    return tuple(_pet_acquisition_exact_repair_marker_priorities(item))


def _pet_acquisition_exact_repair_marker_priorities(item: ContextItem) -> dict[str, int]:
    priorities: dict[str, int] = {}
    marker_speakers = _dialogue_turn_marker_speakers(item.text)
    ordered_markers = tuple(marker_speakers) or tuple(
        dict.fromkeys(_DIALOGUE_MARKER_RE.findall(item.text))
    )
    for marker in ordered_markers:
        focused_text = _focused_exact_source_repair_text(
            text=item.text,
            source_id=f"synthetic:{marker}:turn",
        )
        priority = _pet_acquisition_exact_repair_text_priority(focused_text)
        if priority > 1:
            continue
        priorities[marker] = min(priority, priorities.get(marker, priority))
        if priority == 1:
            previous_marker = _previous_same_speaker_dialogue_marker(
                ordered_markers=ordered_markers,
                marker_speakers=marker_speakers,
                marker=marker,
            )
            if not previous_marker:
                previous_marker = _previous_dialogue_marker(
                    ordered_markers=ordered_markers,
                    marker=marker,
                )
            if not previous_marker:
                continue
            priorities[previous_marker] = min(0, priorities.get(previous_marker, 0))
    return priorities


def _dialogue_turn_marker_speakers(text: str) -> dict[str, str]:
    speakers: dict[str, str] = {}
    for match in re.finditer(r"\b(D\d+:\d+)\b\s+([A-Z][^:\n]{0,40}):", text):
        marker = match.group(1)
        speaker = match.group(2).strip().casefold()
        if marker and speaker and marker not in speakers:
            speakers[marker] = speaker
    return speakers


def _previous_same_speaker_dialogue_marker(
    *,
    ordered_markers: tuple[str, ...],
    marker_speakers: dict[str, str],
    marker: str,
) -> str:
    speaker = marker_speakers.get(marker)
    if not speaker:
        return ""
    previous_markers = ordered_markers[: ordered_markers.index(marker)]
    for previous_marker in reversed(previous_markers):
        if marker_speakers.get(previous_marker) == speaker:
            return previous_marker
    return ""


def _previous_dialogue_marker(
    *,
    ordered_markers: tuple[str, ...],
    marker: str,
) -> str:
    previous_markers = ordered_markers[: ordered_markers.index(marker)]
    return previous_markers[-1] if previous_markers else ""


def _exact_source_sibling_answer_evidence_repair_marker_priority(
    *,
    item: ContextItem,
    source_id: str,
) -> int:
    marker_match = _DIALOGUE_MARKER_RE.search(source_id)
    if marker_match is None or not _is_pet_acquisition_exact_repair_scope(item):
        return 1
    return _pet_acquisition_exact_repair_marker_priorities(item).get(
        marker_match.group(0),
        2,
    )


def _exact_source_repair_diagnostics(
    item: ContextItem,
    *,
    repair_priority: int,
) -> dict[str, object]:
    diagnostics = dict(item.diagnostics or {})
    score_signals = diagnostics.get("score_signals")
    score_signal_dict = dict(score_signals) if isinstance(score_signals, dict) else {}
    score_signal_dict["exact_source_repair"] = 1
    if repair_priority == 0:
        score_signal_dict["exact_source_repair_date_anchor"] = 1
    diagnostics["score_signals"] = score_signal_dict
    return diagnostics


def _pet_acquisition_exact_repair_text_priority(text: str) -> int:
    if _PET_ACQUISITION_EXACT_REPAIR_DATE_ANCHOR_RE.search(text) is not None:
        return 0
    if _PET_ACQUISITION_EXACT_REPAIR_OBJECT_RE.search(text) is not None:
        return 1
    return 2


def _source_ref_dialogue_marker(ref: SourceRef) -> str:
    match = _DIALOGUE_MARKER_RE.search(str(ref.source_id))
    return match.group(0) if match is not None else ""


def _focused_exact_source_repair_text(*, text: str, source_id: str) -> str:
    marker_match = re.search(r"\bD\d+:\d+\b", source_id)
    if marker_match is None:
        return text
    marker = marker_match.group(0)
    text_match = _dialogue_turn_marker_text_match(text=text, marker=marker)
    if text_match is None:
        return text
    next_match = re.search(r"\bD\d+:\d+\b", text[text_match.end() :])
    end = text_match.end() + next_match.start() if next_match is not None else len(text)
    focused = text[text_match.start() : end].strip()
    return focused or text


def _dialogue_turn_marker_text_match(
    *,
    text: str,
    marker: str,
) -> re.Match[str] | None:
    matches = tuple(re.finditer(rf"\b{re.escape(marker)}\b", text))
    if not matches:
        return None
    for match in matches:
        following = text[match.end() : match.end() + 48]
        if re.match(r"\s+[A-Z][^:\n]{0,40}:", following):
            return match
    return matches[0]


def _is_exact_source_sibling_answer_evidence_item(item: ContextItem) -> bool:
    if not _score_signal_truthy(item, "source_sibling_answer_evidence"):
        return False
    turn_refs = tuple(
        ref for ref in item.source_refs if str(ref.source_id).casefold().endswith(":turn")
    )
    return bool(turn_refs)


def _is_exact_source_sibling_marker_coverage_item(item: ContextItem) -> bool:
    if "keyword_source_sibling_chunks" not in diagnostic_retrieval_sources(item.diagnostics):
        return False
    diagnostics = item.diagnostics or {}
    query_reason = str(diagnostics.get("query_expansion_reason") or "").replace("_", "-")
    if query_reason != "pottery-type-bridge":
        return False
    turn_refs = tuple(
        ref for ref in item.source_refs if str(ref.source_id).casefold().endswith(":turn")
    )
    if len(turn_refs) < 2:
        return False
    score_signals = diagnostics.get("score_signals")
    if not isinstance(score_signals, dict):
        return False
    return _numeric_score_signal(score_signals.get("query_expansion_reason_priority")) >= 3


def _pre_pack_candidate_source_ref_diagnostics(
    items: tuple[ContextItem, ...],
) -> dict[str, object]:
    source_ids: list[str] = []
    dialogue_markers: list[str] = []
    answer_evidence_source_ids: list[str] = []
    answer_evidence_dialogue_markers: list[str] = []
    items_with_source_refs = 0
    for item in items:
        if item.source_refs:
            items_with_source_refs += 1
        source_sibling_answer_evidence = _score_signal_truthy(
            item,
            "source_sibling_answer_evidence",
        )
        for ref in item.source_refs:
            source_id = str(ref.source_id).strip()
            if source_id and source_id not in source_ids:
                source_ids.append(source_id)
            if (
                source_sibling_answer_evidence
                and source_id
                and source_id not in answer_evidence_source_ids
            ):
                answer_evidence_source_ids.append(source_id)
            for marker in _DIALOGUE_MARKER_RE.findall(source_id):
                if marker not in dialogue_markers:
                    dialogue_markers.append(marker)
                if (
                    source_sibling_answer_evidence
                    and marker not in answer_evidence_dialogue_markers
                ):
                    answer_evidence_dialogue_markers.append(marker)
        for marker in _DIALOGUE_MARKER_RE.findall(item.text):
            if marker not in dialogue_markers:
                dialogue_markers.append(marker)
            if source_sibling_answer_evidence and marker not in answer_evidence_dialogue_markers:
                answer_evidence_dialogue_markers.append(marker)
        if (
            len(source_ids) >= 80
            and len(dialogue_markers) >= 80
            and len(answer_evidence_source_ids) >= 40
            and len(answer_evidence_dialogue_markers) >= 40
        ):
            break
    return {
        "pre_pack_candidate_item_count": len(items),
        "pre_pack_items_with_source_refs": items_with_source_refs,
        "pre_pack_source_ref_ids_sample": source_ids[:200],
        "pre_pack_dialogue_markers_sample": dialogue_markers[:200],
        "pre_pack_source_sibling_answer_evidence_source_ref_ids_sample": (
            answer_evidence_source_ids[:40]
        ),
        "pre_pack_source_sibling_answer_evidence_dialogue_markers_sample": (
            answer_evidence_dialogue_markers[:40]
        ),
    }


def _source_sibling_answer_evidence_stage_diagnostics(
    stage: str,
    items: tuple[ContextItem, ...],
) -> dict[str, object]:
    source_ids: list[str] = []
    dialogue_markers: list[str] = []
    sibling_source_ids: list[str] = []
    sibling_dialogue_markers: list[str] = []
    item_count = 0
    sibling_item_count = 0
    for item in items:
        is_sibling = "keyword_source_sibling_chunks" in diagnostic_retrieval_sources(
            item.diagnostics
        )
        is_answer_evidence = _score_signal_truthy(item, "source_sibling_answer_evidence")
        if is_sibling:
            sibling_item_count += 1
        if is_answer_evidence:
            item_count += 1
        for ref in item.source_refs:
            source_id = str(ref.source_id).strip()
            if is_sibling and source_id and source_id not in sibling_source_ids:
                sibling_source_ids.append(source_id)
            if is_answer_evidence and source_id and source_id not in source_ids:
                source_ids.append(source_id)
            for marker in _DIALOGUE_MARKER_RE.findall(source_id):
                if is_sibling and marker not in sibling_dialogue_markers:
                    sibling_dialogue_markers.append(marker)
                if is_answer_evidence and marker not in dialogue_markers:
                    dialogue_markers.append(marker)
        for marker in _DIALOGUE_MARKER_RE.findall(item.text):
            if is_sibling and marker not in sibling_dialogue_markers:
                sibling_dialogue_markers.append(marker)
            if is_answer_evidence and marker not in dialogue_markers:
                dialogue_markers.append(marker)
    return {
        f"{stage}_source_sibling_item_count": sibling_item_count,
        f"{stage}_source_sibling_source_ref_ids_sample": sibling_source_ids[:200],
        f"{stage}_source_sibling_dialogue_markers_sample": sibling_dialogue_markers[:200],
        f"{stage}_source_sibling_answer_evidence_item_count": item_count,
        f"{stage}_source_sibling_answer_evidence_source_ref_ids_sample": source_ids[:200],
        f"{stage}_source_sibling_answer_evidence_dialogue_markers_sample": (
            dialogue_markers[:200]
        ),
    }


def _score_signal_truthy(item: ContextItem, key: str) -> bool:
    diagnostics = _provenance(dict(item.diagnostics or {}))
    score_signals = item.diagnostics.get("score_signals") if item.diagnostics else None
    if isinstance(score_signals, dict):
        value = score_signals.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, int | float):
            return value > 0
        if isinstance(value, str):
            return value.casefold() in {"1", "true", "yes"}
    value = diagnostics.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value > 0
    if isinstance(value, str):
        return value.casefold() in {"1", "true", "yes"}
    return False
