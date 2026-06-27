from infinity_context_core.application.context_query_intent import build_query_anchor_intent
from infinity_context_core.application.dto import ContextItem
from infinity_context_core.application.use_cases.build_context import (
    _apply_explicit_requirement_guard,
    _restore_exact_source_sibling_answer_evidence_items,
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


def test_requirement_guard_keeps_cause_awareness_exact_evidence() -> None:
    item = _item(
        "charity_race_awareness",
        (
            "D2:2 Caroline: That charity race sounds great. Raising awareness "
            "for mental health is super rewarding."
        ),
        deterministic_reasons=(
            "relation_requirement_missing_relation",
            "cause_awareness_exact_evidence",
        ),
    )
    query = "What did the charity race raise awareness for?"

    guarded_items, diagnostics = _apply_explicit_requirement_guard(
        query=query,
        query_anchor_intent=build_query_anchor_intent(query),
        items=(item,),
    )

    assert guarded_items == (item,)
    assert diagnostics["requirement_guard_status"] == "satisfied"
    assert diagnostics["requirement_guard_items_dropped"] == 0


def test_requirement_guard_keeps_precise_list_source_sibling_answer_support() -> None:
    item = _item(
        "melanie_book_turn",
        'D6:10 Melanie: I loved reading "Charlotte\'s Web" as a kid.',
        deterministic_reasons=("relation_requirement_missing_relation",),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-26:session_6:D6:10:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "query_expansion_reason_priority": 4,
                "distinctive_term_hits": 6,
                "unique_term_hits": 5,
            },
        },
    )
    query = "What books has Melanie read?"

    guarded_items, diagnostics = _apply_explicit_requirement_guard(
        query=query,
        query_anchor_intent=build_query_anchor_intent(query),
        items=(item,),
    )

    assert guarded_items == (item,)
    assert diagnostics["requirement_guard_status"] == "satisfied"
    assert diagnostics["requirement_guard_items_dropped"] == 0


def test_requirement_guard_still_drops_weak_list_source_sibling_relation_mismatch() -> None:
    item = _item(
        "weak_book_turn",
        "D6:9 Melanie talked about reading in general.",
        deterministic_reasons=("relation_requirement_missing_relation",),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-26:session_6:D6:9:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "query_expansion_reason_priority": 1,
                "distinctive_term_hits": 2,
                "unique_term_hits": 2,
            },
        },
    )
    query = "What books has Melanie read?"

    guarded_items, diagnostics = _apply_explicit_requirement_guard(
        query=query,
        query_anchor_intent=build_query_anchor_intent(query),
        items=(item,),
    )

    assert guarded_items == ()
    assert diagnostics["requirement_guard_status"] == (
        "dropped_relation_requirement_mismatch"
    )
    assert diagnostics["requirement_guard_relation_mismatch_drop_count"] == 1


def test_requirement_guard_keeps_precise_temporal_source_sibling_answer_support() -> None:
    item = _item(
        "museum_yesterday_turn",
        (
            "D6:4 Melanie: Yesterday I took the kids to the museum - it was "
            "so cool spending time with them."
        ),
        deterministic_reasons=("relation_requirement_missing_relation",),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-26:session_6:D6:4:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "distinctive_term_hits": 3,
                "unique_term_hits": 3,
                "source_sibling_closeness": 4,
            },
        },
    )
    query = "When did Melanie go to the museum?"

    guarded_items, diagnostics = _apply_explicit_requirement_guard(
        query=query,
        query_anchor_intent=build_query_anchor_intent(query),
        items=(item,),
    )

    assert guarded_items == (item,)
    assert diagnostics["requirement_guard_status"] == "satisfied"
    assert diagnostics["requirement_guard_items_dropped"] == 0


def test_requirement_guard_keeps_distant_temporal_source_sibling_answer_evidence() -> None:
    item = _item(
        "picnic_last_week_turn",
        (
            "D6:11 Caroline: My friends and family helped with my transition. "
            "They make all the difference. We even had a picnic last week!"
        ),
        deterministic_reasons=("relation_requirement_missing_relation",),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conversation:session_6:D6:11:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "source_sibling_answer_evidence": 1,
                "distinctive_term_hits": 1,
                "unique_term_hits": 1,
                "source_sibling_closeness": 0,
            },
        },
    )
    query = "When did Caroline have a picnic?"

    guarded_items, diagnostics = _apply_explicit_requirement_guard(
        query=query,
        query_anchor_intent=build_query_anchor_intent(query),
        items=(item,),
    )

    assert guarded_items == (item,)
    assert diagnostics["requirement_guard_status"] == "satisfied"
    assert diagnostics["requirement_guard_items_dropped"] == 0


def test_requirement_guard_keeps_temporal_answer_signal_when_snippet_lost_time_phrase() -> None:
    item = _item(
        "picnic_snippet_turn",
        (
            "D6:11 Caroline: My friends and family helped with my transition. "
            "They make all the difference. We even had a picnic."
        ),
        deterministic_reasons=("relation_requirement_missing_relation",),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conversation:session_6:D6:11:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "source_sibling_answer_evidence": 1,
                "distinctive_term_hits": 1,
                "unique_term_hits": 1,
                "source_sibling_closeness": 0,
            },
        },
    )
    query = "When did Caroline have a picnic?"

    guarded_items, diagnostics = _apply_explicit_requirement_guard(
        query=query,
        query_anchor_intent=build_query_anchor_intent(query),
        items=(item,),
    )

    assert guarded_items == (item,)
    assert diagnostics["requirement_guard_status"] == "satisfied"


def test_restore_exact_source_sibling_answer_evidence_repairs_missing_turn_ref() -> None:
    broad_candidate = _item(
        "session_window",
        "D6:5 D6:6 D6:7 ... D6:1 Caroline discussed transition support.",
        deterministic_reasons=(),
        source_refs=(
            SourceRef(
                source_type="locomo_session",
                source_id="locomo:conversation:session_6",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conversation:session_6:D6:4:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_neighbor_chunks",
            "retrieval_sources": ["keyword_neighbor_chunks"],
            "score_signals": {"query_expansion_reason": "decomposition_temporal_answer"},
        },
    )
    exact_source = _item(
        "picnic_last_week_turn",
        (
            "D6:11 Caroline: My friends and family helped with my transition. "
            "They make all the difference. We even had a picnic last week!"
        ),
        deterministic_reasons=(),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conversation:session_6:D6:11:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "source_sibling_answer_evidence": 1,
                "query_expansion_reason": "decomposition_temporal_answer",
            },
        },
    )

    restored, diagnostics = _restore_exact_source_sibling_answer_evidence_items(
        candidates=(broad_candidate,),
        source_items=(broad_candidate, exact_source),
    )

    restored_source_ids = {
        ref.source_id for item in restored for ref in item.source_refs
    }
    assert "locomo:conversation:session_6:D6:11:turn" in restored_source_ids
    assert diagnostics["exact_source_sibling_answer_evidence_repair_added"] == 1


def test_restore_exact_source_sibling_answer_evidence_prioritizes_pet_date_anchor_before_cap() -> None:
    filler_refs = tuple(
        SourceRef(
            source_type="locomo_turn",
            source_id=f"locomo:conv-fixture:session_9:D9:{index}:turn",
        )
        for index in range(100, 270)
    )
    pet_window = _item(
        "session_9_pet_window",
        (
            "session_9 observations\n"
            "D9:2 Dana: Dana has been revising and perfecting a recipe for "
            "her family. Related turns: D9:4.\n"
            "D9:4 Dana: Dana has a stuffed animal dog named Pippa that was "
            "a gift from Sam. Related turns: D9:6 D9:8."
        ),
        deterministic_reasons=(),
        source_refs=(
            *filler_refs,
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_9:D9:4:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "source_sibling_answer_evidence": 1,
                "query_expansion_reason": "pet_acquisition_date_bridge",
            },
        },
    )

    restored, diagnostics = _restore_exact_source_sibling_answer_evidence_items(
        candidates=(),
        source_items=(pet_window,),
    )

    restored_source_ids = {
        ref.source_id for item in restored for ref in item.source_refs
    }
    assert "locomo:conv-fixture:session_9:D9:2:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_9:D9:4:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_9:D9:100:turn" not in restored_source_ids
    assert diagnostics["exact_source_sibling_answer_evidence_repair_added"] == 2


def test_restore_exact_source_sibling_answer_evidence_filters_animal_care_repairs() -> None:
    care_window = _item(
        "session_5_care_window",
        (
            "D5:4 Nate image caption: a photography of two tortoises laying on "
            "the ground in a jungle.\n"
            "D5:8 Nate: No, not really. Just keep their area clean, feed them "
            "properly, and make sure they get enough light. It's actually kind of fun."
        ),
        deterministic_reasons=(),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_5:D5:4:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_5:D5:8:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "source_sibling_answer_evidence": 1,
                "query_expansion_reason": "animal_care_instruction_bridge",
            },
        },
    )

    restored, diagnostics = _restore_exact_source_sibling_answer_evidence_items(
        candidates=(),
        source_items=(care_window,),
    )

    restored_source_ids = {
        ref.source_id for item in restored for ref in item.source_refs
    }
    assert "locomo:conv-fixture:session_5:D5:8:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_5:D5:4:turn" not in restored_source_ids
    assert diagnostics["exact_source_sibling_answer_evidence_repair_added"] == 1


def test_restore_exact_source_sibling_answer_evidence_filters_volunteering_people_repairs() -> None:
    volunteering_window = _item(
        "session_6_volunteering_window",
        (
            "D6:4 Riley volunteers at a neighborhood shelter on weekends.\n"
            "D6:8 Riley: One of the shelter residents, Morgan, wrote a letter "
            "expressing gratitude for the support they receive."
        ),
        deterministic_reasons=(),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_6:D6:4:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_6:D6:8:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "source_sibling_answer_evidence": 1,
                "query_expansion_reason": "volunteering_people_inventory_bridge",
            },
        },
    )

    restored, diagnostics = _restore_exact_source_sibling_answer_evidence_items(
        candidates=(),
        source_items=(volunteering_window,),
    )

    restored_source_ids = {
        ref.source_id for item in restored for ref in item.source_refs
    }
    assert "locomo:conv-fixture:session_6:D6:8:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_6:D6:4:turn" not in restored_source_ids
    assert diagnostics["exact_source_sibling_answer_evidence_repair_added"] == 1


def test_restore_exact_source_sibling_answer_evidence_filters_support_origin_repairs() -> None:
    support_window = _item(
        "session_3_support_window",
        (
            "D3:5 Riley: I have been blessed with love and support throughout "
            "this journey, and I want to pass it on to others.\n"
            "D3:11 Riley: My friends, family, and mentors are my rocks and "
            "give me strength to push on."
        ),
        deterministic_reasons=(),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_3:D3:11:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_3:D3:5:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "source_sibling_answer_evidence": 1,
                "query_expansion_reason": "support_origin_bridge",
            },
        },
    )

    restored, diagnostics = _restore_exact_source_sibling_answer_evidence_items(
        candidates=(),
        source_items=(support_window,),
    )

    restored_source_ids = {
        ref.source_id for item in restored for ref in item.source_refs
    }
    assert "locomo:conv-fixture:session_3:D3:5:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_3:D3:11:turn" not in restored_source_ids
    assert diagnostics["exact_source_sibling_answer_evidence_repair_added"] == 1


def test_restore_exact_source_sibling_answer_evidence_filters_preference_repairs() -> None:
    music_window = _item(
        "session_5_music_window",
        (
            "D5:7 Morgan: The outdoor festival was crowded.\n"
            "D5:9 Morgan: I'm a fan of classical music like Bach and Mozart, "
            "and I also enjoy modern songs."
        ),
        deterministic_reasons=(),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_5:D5:7:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_5:D5:9:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "source_sibling_answer_evidence": 1,
                "query_expansion_reason": "classical_music_preference_bridge",
            },
        },
    )

    restored, diagnostics = _restore_exact_source_sibling_answer_evidence_items(
        candidates=(),
        source_items=(music_window,),
    )

    restored_source_ids = {
        ref.source_id for item in restored for ref in item.source_refs
    }
    assert "locomo:conv-fixture:session_5:D5:9:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_5:D5:7:turn" not in restored_source_ids
    assert diagnostics["exact_source_sibling_answer_evidence_repair_added"] == 1


def test_restore_exact_source_sibling_answer_evidence_filters_reminder_repairs() -> None:
    reminder_window = _item(
        "session_4_reminder_window",
        (
            "D4:3 Riley: I painted a lake scene last weekend.\n"
            "D4:5 Riley: The handmade bowl has sentimental value. Its pattern "
            "and colors remind me of art and self-expression."
        ),
        deterministic_reasons=(),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_4:D4:3:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_4:D4:5:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "source_sibling_answer_evidence": 1,
                "query_expansion_reason": "sentimental_reminder_bridge",
            },
        },
    )

    restored, diagnostics = _restore_exact_source_sibling_answer_evidence_items(
        candidates=(),
        source_items=(reminder_window,),
    )

    restored_source_ids = {
        ref.source_id for item in restored for ref in item.source_refs
    }
    assert "locomo:conv-fixture:session_4:D4:5:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_4:D4:3:turn" not in restored_source_ids
    assert diagnostics["exact_source_sibling_answer_evidence_repair_added"] == 1


def test_restore_exact_source_sibling_answer_evidence_filters_outdoor_preference_repairs() -> None:
    outdoor_window = _item(
        "session_10_outdoor_window",
        (
            "D10:10 Morgan: We picked up snacks for the weekend.\n"
            "D10:12 Morgan: We always look forward to our family camping trip. "
            "We roast marshmallows around the campfire; it is the highlight "
            "of our summer.\n"
            "D10:14 Morgan: I'll always remember the camping trip when we saw "
            "a meteor shower and felt at one with the universe."
        ),
        deterministic_reasons=(),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_10:D10:10:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_10:D10:12:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_10:D10:14:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "source_sibling_answer_evidence": 1,
                "query_expansion_reason": "outdoor_preference_bridge",
            },
        },
    )

    restored, diagnostics = _restore_exact_source_sibling_answer_evidence_items(
        candidates=(),
        source_items=(outdoor_window,),
    )

    restored_source_ids = {
        ref.source_id for item in restored for ref in item.source_refs
    }
    assert "locomo:conv-fixture:session_10:D10:12:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_10:D10:14:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_10:D10:10:turn" not in restored_source_ids
    assert diagnostics["exact_source_sibling_answer_evidence_repair_added"] == 2


def test_restore_exact_source_sibling_answer_evidence_filters_children_preference_repairs() -> None:
    preference_window = _item(
        "session_children_preference_window",
        (
            "D4:7 Avery: We packed snacks for the drive.\n"
            "D4:8 Avery: The younger kids love nature, campfires, and "
            "hiking outdoors.\n"
            "D6:6 Avery: They were stoked for the dinosaur exhibit. "
            "They love learning about animals and the bones were cool.\n"
            "D6:7 Avery: I need to update the family calendar."
        ),
        deterministic_reasons=(),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_4:D4:7:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_4:D4:8:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_6:D6:6:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_6:D6:7:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "source_sibling_answer_evidence": 1,
                "query_expansion_reason": "children_preference_bridge",
            },
        },
    )

    restored, diagnostics = _restore_exact_source_sibling_answer_evidence_items(
        candidates=(),
        source_items=(preference_window,),
    )

    restored_source_ids = {
        ref.source_id for item in restored for ref in item.source_refs
    }
    assert "locomo:conv-fixture:session_4:D4:8:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_6:D6:6:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_4:D4:7:turn" not in restored_source_ids
    assert "locomo:conv-fixture:session_6:D6:7:turn" not in restored_source_ids
    assert diagnostics["exact_source_sibling_answer_evidence_repair_added"] == 2


def test_restore_exact_source_sibling_answer_evidence_filters_activity_repairs() -> None:
    activity_window = _item(
        "session_activity_window",
        (
            "D5:4 Avery: I just signed up for a pottery class yesterday. "
            "It lets me express myself and get creative.\n"
            "D5:6 Avery: I'm a big fan of pottery; the creativity is awesome.\n"
            "D9:1 Avery: I went camping with my family and enjoyed unplugging "
            "with the kids.\n"
            "D1:18 Avery: I'm off to go swimming with the kids."
        ),
        deterministic_reasons=(),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_5:D5:4:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_5:D5:6:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_9:D9:1:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_1:D1:18:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "source_sibling_answer_evidence": 1,
                "query_expansion_reason": "decomposition_activity_participation",
            },
        },
    )

    restored, diagnostics = _restore_exact_source_sibling_answer_evidence_items(
        candidates=(),
        source_items=(activity_window,),
    )

    restored_source_ids = {
        ref.source_id for item in restored for ref in item.source_refs
    }
    assert "locomo:conv-fixture:session_5:D5:4:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_9:D9:1:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_1:D1:18:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_5:D5:6:turn" not in restored_source_ids
    assert diagnostics["exact_source_sibling_answer_evidence_repair_added"] == 3


def test_restore_exact_source_sibling_answer_evidence_filters_exercise_companion_repairs() -> None:
    activity_window = _item(
        "session_exercise_window",
        (
            "D4:2 Riley: I started a weekend yoga class with a colleague. "
            "It helps me feel more flexible.\n"
            "D4:3 Riley: Yoga improves my focus and breathing after work.\n"
            "D7:8 Riley: My colleague Alex invited me to a beginner yoga class.\n"
            "D7:9 Riley: The studio has calm music and good lighting.\n"
            "D8:5 Riley: I started vinyasa yoga at a small studio downtown.\n"
            "D8:6 Riley: Yoga helps me stretch after work."
        ),
        deterministic_reasons=(),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_4:D4:2:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_4:D4:3:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_7:D7:8:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_7:D7:9:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_8:D8:5:turn",
            ),
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_8:D8:6:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "source_sibling_answer_evidence": 1,
                "query_expansion_reason": "exercise_activity_inventory_bridge",
            },
        },
    )

    restored, diagnostics = _restore_exact_source_sibling_answer_evidence_items(
        candidates=(),
        source_items=(activity_window,),
    )

    restored_source_ids = {
        ref.source_id for item in restored for ref in item.source_refs
    }
    assert "locomo:conv-fixture:session_4:D4:2:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_7:D7:8:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_8:D8:5:turn" in restored_source_ids
    assert "locomo:conv-fixture:session_4:D4:3:turn" not in restored_source_ids
    assert "locomo:conv-fixture:session_7:D7:9:turn" not in restored_source_ids
    assert "locomo:conv-fixture:session_8:D8:6:turn" not in restored_source_ids
    assert diagnostics["exact_source_sibling_answer_evidence_repair_added"] == 3


def test_requirement_guard_still_drops_weak_temporal_source_sibling_relation_mismatch() -> None:
    item = _item(
        "generic_recent_turn",
        "D6:9 Melanie said the week was busy but did not mention the museum.",
        deterministic_reasons=("relation_requirement_missing_relation",),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-26:session_6:D6:9:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "distinctive_term_hits": 1,
                "unique_term_hits": 1,
                "source_sibling_closeness": 1,
            },
        },
    )
    query = "When did Melanie go to the museum?"

    guarded_items, diagnostics = _apply_explicit_requirement_guard(
        query=query,
        query_anchor_intent=build_query_anchor_intent(query),
        items=(item,),
    )

    assert guarded_items == ()
    assert diagnostics["requirement_guard_status"] == (
        "dropped_relation_requirement_mismatch"
    )
    assert diagnostics["requirement_guard_relation_mismatch_drop_count"] == 1


def test_requirement_guard_keeps_precise_activity_companion_source_sibling() -> None:
    item = _item(
        "activity_companion_turn",
        (
            "D4:2 Riley: My colleague Alex invited me to a beginner yoga class "
            "after work."
        ),
        deterministic_reasons=("relation_requirement_missing_relation",),
        source_refs=(
            SourceRef(
                source_type="locomo_turn",
                source_id="locomo:conv-fixture:session_4:D4:2:turn",
            ),
        ),
        diagnostics={
            "retrieval_source": "keyword_source_sibling_chunks",
            "retrieval_sources": ["keyword_source_sibling_chunks"],
            "score_signals": {
                "source_sibling_answer_evidence": 1,
                "query_expansion_reason": "exercise_activity_inventory_bridge",
            },
        },
    )
    query = "Who did Riley go to yoga with?"

    guarded_items, diagnostics = _apply_explicit_requirement_guard(
        query=query,
        query_anchor_intent=build_query_anchor_intent(query),
        items=(item,),
    )

    assert guarded_items == (item,)
    assert diagnostics["requirement_guard_status"] == "satisfied"
    assert diagnostics["requirement_guard_relation_mismatch_drop_count"] == 0


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
    source_refs: tuple[SourceRef, ...] | None = None,
    diagnostics: dict[str, object] | None = None,
) -> ContextItem:
    item_diagnostics = {
        "retrieval_source": "keyword_chunks",
        "retrieval_sources": ["keyword_chunks"],
        "provenance": {
            "deterministic_rerank_reasons": list(deterministic_reasons),
        },
    }
    if diagnostics:
        item_diagnostics.update(diagnostics)
        provenance = dict(item_diagnostics.get("provenance", {}))
        provenance["deterministic_rerank_reasons"] = list(deterministic_reasons)
        item_diagnostics["provenance"] = provenance
    return ContextItem(
        item_id=item_id,
        item_type="chunk",
        text=text,
        score=0.7,
        source_refs=source_refs or (SourceRef(source_type="document", source_id="doc"),),
        diagnostics=item_diagnostics,
    )
