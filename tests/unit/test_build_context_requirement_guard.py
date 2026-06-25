from infinity_context_core.application.context_query_intent import build_query_anchor_intent
from infinity_context_core.application.dto import ContextItem
from infinity_context_core.application.use_cases.build_context import (
    _apply_explicit_requirement_guard,
)
from infinity_context_core.domain.entities import SourceRef


def test_requirement_guard_drops_object_kind_mismatch_evidence() -> None:
    item = _item(
        "cat_note",
        "I mentioned my cat Luna during the call.",
        deterministic_reasons=("object_kind_species_mismatch",),
    )

    guarded_items, diagnostics = _apply_explicit_requirement_guard(
        query="What hamster did I mention?",
        query_anchor_intent=build_query_anchor_intent("What hamster did I mention?"),
        items=(item,),
    )

    assert guarded_items == ()
    assert diagnostics["requirement_guard_status"] == "dropped_object_kind_mismatch"
    assert diagnostics["requirement_guard_items_dropped"] == 1
    assert diagnostics["requirement_guard_object_kind_mismatch_drop_count"] == 1


def test_requirement_guard_keeps_object_kind_match_evidence() -> None:
    item = _item(
        "hamster_note",
        "I mentioned my hamster Pip during the call.",
        deterministic_reasons=("object_kind_match",),
    )

    guarded_items, diagnostics = _apply_explicit_requirement_guard(
        query="What hamster did I mention?",
        query_anchor_intent=build_query_anchor_intent("What hamster did I mention?"),
        items=(item,),
    )

    assert guarded_items == (item,)
    assert diagnostics["requirement_guard_status"] == "satisfied"
    assert diagnostics["requirement_guard_items_dropped"] == 0


def test_requirement_guard_drops_relation_requirement_mismatch_evidence() -> None:
    item = _item(
        "alex_atlas_anchor_only",
        "Alex and Project Atlas appeared in the planning summary.",
        deterministic_reasons=("relation_requirement_missing_relation",),
    )
    query = "Did Alex ever mention Project Atlas?"

    guarded_items, diagnostics = _apply_explicit_requirement_guard(
        query=query,
        query_anchor_intent=build_query_anchor_intent(query),
        items=(item,),
    )

    assert guarded_items == ()
    assert diagnostics["requirement_guard_status"] == (
        "dropped_relation_requirement_mismatch"
    )
    assert diagnostics["requirement_guard_items_dropped"] == 1
    assert diagnostics["requirement_guard_relation_mismatch_drop_count"] == 1


def test_requirement_guard_drops_relation_requirement_object_mismatch_evidence() -> None:
    item = _item(
        "alex_mentioned_apollo",
        "Alex mentioned Project Apollo during the billing call.",
        deterministic_reasons=("relation_requirement_object_mismatch",),
    )
    query = "Did Alex ever mention Project Atlas?"

    guarded_items, diagnostics = _apply_explicit_requirement_guard(
        query=query,
        query_anchor_intent=build_query_anchor_intent(query),
        items=(item,),
    )

    assert guarded_items == ()
    assert diagnostics["requirement_guard_status"] == (
        "dropped_relation_requirement_mismatch"
    )
    assert diagnostics["requirement_guard_items_dropped"] == 1
    assert diagnostics["requirement_guard_relation_mismatch_drop_count"] == 1


def test_requirement_guard_keeps_relation_requirement_match_evidence() -> None:
    item = _item(
        "alex_mentioned_atlas",
        "Alex mentioned Project Atlas during the billing call.",
        deterministic_reasons=("relation_requirement_match",),
    )
    query = "Did Alex ever mention Project Atlas?"

    guarded_items, diagnostics = _apply_explicit_requirement_guard(
        query=query,
        query_anchor_intent=build_query_anchor_intent(query),
        items=(item,),
    )

    assert guarded_items == (item,)
    assert diagnostics["requirement_guard_status"] == "satisfied"
    assert diagnostics["requirement_guard_items_dropped"] == 0


def test_requirement_guard_keeps_domain_exact_evidence_for_relation_shape() -> None:
    item = _item(
        "melanie_pottery_cups",
        "D8:4 Melanie: My kids and I made clay cups in pottery class.",
        deterministic_reasons=(
            "relation_requirement_missing_relation",
            "inventory_list_exact_evidence",
        ),
    )
    query = "What types of pottery have Melanie and her kids made?"

    guarded_items, diagnostics = _apply_explicit_requirement_guard(
        query=query,
        query_anchor_intent=build_query_anchor_intent(query),
        items=(item,),
    )

    assert guarded_items == (item,)
    assert diagnostics["requirement_guard_status"] == "satisfied"
    assert diagnostics["requirement_guard_items_dropped"] == 0


def test_requirement_guard_drops_missing_count_answer_shape_evidence() -> None:
    item = _item(
        "generic_pet_note",
        "Gina loves pets and volunteers at the shelter.",
        deterministic_reasons=("explicit_answer_shape_missing",),
    )
    query = "How many pets does Gina have?"

    guarded_items, diagnostics = _apply_explicit_requirement_guard(
        query=query,
        query_anchor_intent=build_query_anchor_intent(query),
        items=(item,),
    )

    assert guarded_items == ()
    assert diagnostics["requirement_guard_status"] == "dropped_missing_count_answer_shape"
    assert diagnostics["requirement_guard_items_dropped"] == 1
    assert diagnostics["requirement_guard_count_answer_shape_missing_drop_count"] == 1


def test_requirement_guard_keeps_count_answer_shape_evidence() -> None:
    item = _item(
        "enumerated_pet_note",
        "Gina has a rescue dog, a cat, and a turtle at home.",
        deterministic_reasons=("explicit_requirement_covered",),
    )
    query = "How many pets does Gina have?"

    guarded_items, diagnostics = _apply_explicit_requirement_guard(
        query=query,
        query_anchor_intent=build_query_anchor_intent(query),
        items=(item,),
    )

    assert guarded_items == (item,)
    assert diagnostics["requirement_guard_status"] == "satisfied"
    assert diagnostics["requirement_guard_items_dropped"] == 0


def _item(
    item_id: str,
    text: str,
    *,
    deterministic_reasons: tuple[str, ...],
) -> ContextItem:
    return ContextItem(
        item_id=item_id,
        item_type="chunk",
        text=text,
        score=0.7,
        source_refs=(SourceRef(source_type="document", source_id="doc"),),
        diagnostics={
            "retrieval_source": "keyword_chunks",
            "retrieval_sources": ["keyword_chunks"],
            "provenance": {
                "deterministic_rerank_reasons": list(deterministic_reasons),
            },
        },
    )
