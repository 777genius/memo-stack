from datetime import UTC, datetime

from infinity_context_core.application.context_query_expansion import (
    build_query_expansion_plan,
)
from infinity_context_core.application.context_relevance import QueryRelevance
from infinity_context_core.application.context_source_siblings import (
    is_precise_source_sibling_turn,
    source_group_seed_turns,
    source_sibling_answer_evidence,
    source_sibling_candidate_limit,
    source_sibling_distant_answer_evidence_rank,
    source_sibling_relevance_allowed,
    source_sibling_score_cap,
)
from infinity_context_core.application.use_cases.build_context import (
    _prioritize_source_sibling_answer_evidence_seed_chunks,
)
from infinity_context_core.domain.entities import (
    LifecycleStatus,
    MemoryChunk,
    MemoryChunkKind,
)


def test_source_sibling_answer_evidence_accepts_generic_list_slot_match() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="What music events has John attended?",
        expansion_reason="music_event_inventory_bridge",
        text=(
            "D20:4: Maria: Last week, we had a blast at a live music event. "
            "Seeing them enjoy the songs made the night special."
        ),
    )


def test_source_sibling_answer_evidence_accepts_church_friend_activity_wording() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="What activities has Riley done with church friends?",
        expansion_reason="church_friend_activity_inventory_bridge",
        text=(
            "D4:2 Riley: Last weekend I had a picnic with friends from church. "
            "We played games and ate outside."
        ),
    )
    assert source_sibling_answer_evidence(
        expansion_query="What activities has Riley done with church friends?",
        expansion_reason="church_friend_activity_inventory_bridge",
        text=(
            "D6:8 Riley: Yesterday I took up community work with my friends "
            "from church. It was super rewarding."
        ),
    )
    assert not source_sibling_answer_evidence(
        expansion_query="What activities has Riley done with church friends?",
        expansion_reason="church_friend_activity_inventory_bridge",
        text="D7:1 Riley: I joined a local church and met friendly people.",
    )


def test_source_sibling_answer_evidence_accepts_activity_competition_proof() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="Did Riley and Jordan both participate in chess competitions?",
        expansion_reason="activity_competition_evidence_bridge",
        text=(
            "D4:2 Riley: Here's one of my trophies from a chess contest, "
            "a reminder of the hard work and joy it brings."
        ),
    )
    assert not source_sibling_answer_evidence(
        expansion_query="Did Riley and Jordan both participate in chess competitions?",
        expansion_reason="activity_competition_evidence_bridge",
        text="D4:3 Riley: I watched a chess match on television.",
    )


def test_source_sibling_answer_evidence_accepts_direct_item_purchases() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="What items has Melanie bought?",
        expansion_reason="item_purchase_bridge",
        text=(
            "D7:18 Melanie: Luna and Oliver are sweet and playful. "
            "Just got some new shoes, too!"
        ),
    )
    assert source_sibling_answer_evidence(
        expansion_query="What items has Melanie bought?",
        expansion_reason="item_purchase_bridge",
        text="D19:2 Melanie: These figurines I bought yesterday remind me of family love.",
    )
    assert not source_sibling_answer_evidence(
        expansion_query="What items has Melanie bought?",
        expansion_reason="item_purchase_bridge",
        text="D8:3 Caroline: I bought new shoes for the trip.",
    )


def test_source_sibling_answer_evidence_accepts_business_commonality_turns() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="What do Jon and Gina both have in common?",
        expansion_reason="business_commonality_bridge",
        text=(
            "D2:1 Gina: I launched an ad campaign for my clothing store in "
            "hopes of growing the business. Starting my own store is scary."
        ),
    )
    assert source_sibling_answer_evidence(
        expansion_query="Do Jon and Gina start businesses out of what they love?",
        expansion_reason="business_start_reason_bridge",
        text=(
            "D6:8 Gina: I'm passionate about fashion trends and finding unique "
            "pieces. I wanted to blend my love for dance and fashion."
        ),
    )


def test_source_sibling_answer_evidence_accepts_family_support_appreciation() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="How did Melanie feel about her family supporting her?",
        expansion_reason="post_event_emotion_bridge",
        text="D18:13 Melanie: Thanks, Caroline. They're a real support. Appreciate them a lot.",
    )


def test_source_sibling_answer_evidence_accepts_direct_cause_inventory() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="What causes does John feel passionate about supporting?",
        expansion_reason="cause_education_infrastructure_inventory_bridge",
        text=(
            "D1:8 John: I'm passionate about improving education and "
            "infrastructure in our community. Those are my main focuses."
        ),
    )
    assert source_sibling_answer_evidence(
        expansion_query="What causes does John feel passionate about supporting?",
        expansion_reason="cause_education_infrastructure_inventory_bridge",
        text=(
            "D12:5 John: Recently, education reform and infrastructure "
            "development. Good access to quality education is key."
        ),
    )
    assert source_sibling_answer_evidence(
        expansion_query="What causes does John feel passionate about supporting?",
        expansion_reason="cause_veterans_inventory_bridge",
        text="D15:3 John: I've always been passionate about veterans and their rights.",
    )


def test_source_sibling_answer_evidence_accepts_fundraiser_event_slots() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="What events is Taylor planning for the community fundraiser?",
        expansion_reason="event_participation_bridge",
        text=(
            "D3:8 Taylor: I'm currently planning a beanbag tournament for the "
            "community center's fundraiser later this month."
        ),
    )
    assert source_sibling_answer_evidence(
        expansion_query="What events is Taylor planning for the community fundraiser?",
        expansion_reason="event_participation_bridge",
        text=(
            "D4:2 Taylor: I'm busy at the center getting ready for a fundraiser "
            "next week. Hopefully, we can raise enough to cover basic supplies."
        ),
    )


def test_source_sibling_answer_evidence_accepts_activity_class_companion() -> None:
    assert source_sibling_answer_evidence(
        expansion_query=(
            "yoga type types style styles practiced practice practicing class "
            "classes started starting trying tried poses breathing meditation"
        ),
        expansion_reason="exercise_activity_inventory_bridge",
        text=(
            "D4:2 Riley: I started a weekend yoga class with a colleague, "
            "and it has been great for flexibility."
        ),
    )
    assert source_sibling_answer_evidence(
        expansion_query=(
            "yoga type types style styles practiced practice practicing class "
            "classes started starting trying tried poses breathing meditation"
        ),
        expansion_reason="exercise_activity_inventory_bridge",
        text=(
            "D4:3 Riley: My colleague Alex invited me to a beginner yoga class "
            "after work."
        ),
    )


def test_source_sibling_answer_evidence_rejects_activity_without_companion() -> None:
    assert not source_sibling_answer_evidence(
        expansion_query=(
            "yoga type types style styles practiced practice practicing class "
            "classes started starting trying tried poses breathing meditation"
        ),
        expansion_reason="exercise_activity_inventory_bridge",
        text="D4:4 Riley: Yoga helps my flexibility, so I practice after work.",
    )


def test_volunteering_inventory_accepts_named_person_evidence() -> None:
    text = (
        "D6:8 Riley: One of the shelter residents, Morgan, wrote a letter "
        "expressing gratitude for the support they receive."
    )
    chunk = _chunk(
        chunk_id="resident-letter",
        source_external_id="locomo:conv-fixture:session_6:D6:8:turn",
        sequence=8,
        text=text,
    )

    assert source_sibling_answer_evidence(
        expansion_query="What people has Riley met and helped while volunteering?",
        expansion_reason="volunteering_inventory_bridge",
        text=text,
    )
    assert is_precise_source_sibling_turn(
        chunk=chunk,
        expansion_reason="volunteering_inventory_bridge",
    )
    assert source_sibling_score_cap(
        expansion_reason="volunteering_inventory_bridge",
        relevance=QueryRelevance(
            score_boost=0.02,
            query_term_count=9,
            unique_term_hits=2,
            capped_frequency_hits=2,
            hit_ratio=0.22,
            distinctive_term_count=7,
            distinctive_term_hits=2,
        ),
        text=text,
    ) is None
    assert source_sibling_answer_evidence(
        expansion_query="What people has Riley met and helped while volunteering?",
        expansion_reason="volunteering_people_inventory_bridge",
        text=text,
    )
    assert is_precise_source_sibling_turn(
        chunk=chunk,
        expansion_reason="volunteering_people_inventory_bridge",
    )
    assert source_sibling_score_cap(
        expansion_reason="volunteering_people_inventory_bridge",
        relevance=QueryRelevance(
            score_boost=0.02,
            query_term_count=9,
            unique_term_hits=2,
            capped_frequency_hits=2,
            hit_ratio=0.22,
            distinctive_term_count=7,
            distinctive_term_hits=2,
        ),
        text=text,
    ) is None


def test_volunteering_inventory_rejects_generic_shelter_mention() -> None:
    assert not source_sibling_answer_evidence(
        expansion_query="What people has Riley met and helped while volunteering?",
        expansion_reason="volunteering_inventory_bridge",
        text="D5:1 Riley volunteers at a neighborhood shelter on weekends.",
    )


def test_answer_evidence_seed_priority_keeps_late_volunteering_person_group() -> None:
    noise_chunks = tuple(
        _chunk(
            chunk_id=f"generic-volunteer-{index}",
            source_external_id=(
                f"locomo:conv-fixture:session_{index}:D{index}:1:turn"
            ),
            sequence=index,
            text=(
                f"D{index}:1 Riley volunteers at a community shelter on weekends "
                "and says the work is rewarding."
            ),
        )
        for index in range(1, 40)
    )
    resident_letter = _chunk(
        chunk_id="resident-gratitude-letter",
        source_external_id="locomo:conv-fixture:session_50:D50:8:turn",
        sequence=8,
        text=(
            "D50:8 Riley: One of the residents at the shelter wrote a heartfelt "
            "expression of gratitude about the impact of the support they receive."
        ),
    )

    unprioritized_groups = source_group_seed_turns((*noise_chunks, resident_letter))
    prioritized_chunks = _prioritize_source_sibling_answer_evidence_seed_chunks(
        seed_chunks=(*noise_chunks, resident_letter),
        query_plan=build_query_expansion_plan(
            "What people has Riley met and helped while volunteering?"
        ),
        query_relevance_cache={},
    )
    prioritized_groups = source_group_seed_turns(prioritized_chunks)

    assert "locomo:conv-fixture:session_50" not in unprioritized_groups
    assert "locomo:conv-fixture:session_50" in prioritized_groups


def test_source_sibling_answer_evidence_accepts_outdoor_waterfall_visual_slot() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="What outdoor activities has John done with his colleagues?",
        expansion_reason="outdoor_activity_inventory_bridge",
        text=(
            "D16:2 John image caption: a photo of a person standing in front "
            "of a waterfall with colleagues."
        ),
    )


def test_source_sibling_answer_evidence_accepts_outdoor_visual_group_response() -> None:
    assert source_sibling_answer_evidence(
        expansion_query=(
            "Riley outdoor activities hiking camping nature trail colleagues "
            "friends team group people photo image visual waterfall"
        ),
        expansion_reason="outdoor_activity_inventory_bridge",
        text=(
            "D4:2 Riley: Cool that it went well - you and your friends look "
            "like a great team."
        ),
    )


def test_outdoor_activity_visual_response_is_precise_uncapped_sibling() -> None:
    chunk = _chunk(
        chunk_id="outdoor-response",
        source_external_id="locomo:conv-41:session_16:D16:2:turn",
        sequence=2,
        text=(
            "D16:2 Riley: Cool that it went well - you and your friends look "
            "like a great team."
        ),
    )

    assert is_precise_source_sibling_turn(
        chunk=chunk,
        expansion_reason="outdoor_activity_inventory_bridge",
    )
    assert source_sibling_score_cap(
        expansion_reason="outdoor_activity_inventory_bridge",
        relevance=QueryRelevance(
            score_boost=0.02,
            query_term_count=12,
            unique_term_hits=3,
            capped_frequency_hits=3,
            hit_ratio=0.25,
            distinctive_term_count=10,
            distinctive_term_hits=3,
        ),
        text=chunk.text,
    ) is None


def test_source_sibling_answer_evidence_accepts_attribute_family_support() -> None:
    assert source_sibling_answer_evidence(
        expansion_query=(
            "John attributes describe family rock tough times cheer love thankful "
            "family time centered support strength motivation grounded"
        ),
        expansion_reason="attribute_family_support_bridge",
        text=(
            "D2:14 John: They are my rock in tough times and always cheer me on. "
            "I'm really thankful for their love. Family time means a lot to me."
        ),
    )


def test_source_sibling_answer_evidence_rejects_generic_family_mention() -> None:
    assert not source_sibling_answer_evidence(
        expansion_query=(
            "John attributes describe family rock tough times cheer love thankful "
            "family time centered support strength motivation grounded"
        ),
        expansion_reason="attribute_family_support_bridge",
        text="D2:1 John: My family went to the park and played games together.",
    )


def test_source_sibling_answer_evidence_accepts_temporal_turn_support() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="When did Melanie go to the museum?",
        expansion_reason="original_query",
        text=(
            "D6:4 Melanie: Yesterday I took the kids to the museum - it was "
            "so cool spending time with them."
        ),
    )


def test_source_sibling_answer_evidence_accepts_cause_awareness_answer_turn() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="What did the charity race raise awareness for?",
        expansion_reason="cause_awareness_event_bridge",
        text=(
            "D2:2 Riley: That charity race sounds great. Raising awareness "
            "for mental health is rewarding."
        ),
    )


def test_source_sibling_answer_evidence_accepts_running_benefit_turn() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="What does Caroline say running has been great for?",
        expansion_reason="running_reason_bridge",
        text=(
            "D7:24 Melanie: Thanks, Caroline! This has been great for my "
            "mental health. I'm gonna keep running."
        ),
    )


def test_source_sibling_answer_evidence_accepts_frequency_turn_without_speaker() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="How often does Caroline go to the beach with her kids?",
        expansion_reason="decomposition_frequency_recurrence",
        text=(
            "D10:10 Melanie: Seeing my kids' faces so happy at the beach was "
            "the best! We don't go often, usually only once or twice a year."
        ),
    )


def test_source_sibling_answer_evidence_rejects_cause_awareness_event_only_turn() -> None:
    assert not source_sibling_answer_evidence(
        expansion_query="What did the charity race raise awareness for?",
        expansion_reason="cause_awareness_event_bridge",
        text=(
            "D2:1 Avery: I ran a charity race for mental health last Saturday. "
            "It was really rewarding."
        ),
    )


def test_source_sibling_answer_evidence_accepts_classical_music_preference_turn() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="Would Morgan enjoy a classical song by Vivaldi?",
        expansion_reason="classical_music_preference_bridge",
        text=(
            "D5:9 Morgan: I'm a fan of classical music like Bach and Mozart, "
            "and I also enjoy modern songs."
        ),
    )


def test_source_sibling_answer_evidence_accepts_sentimental_reminder_turn() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="What is Riley's handmade bowl a reminder of?",
        expansion_reason="sentimental_reminder_bridge",
        text=(
            "D4:5 Riley: The handmade bowl has sentimental value. Its pattern "
            "and colors remind me of art and self-expression."
        ),
    )


def test_source_sibling_answer_evidence_accepts_outdoor_preference_turns() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="Would Morgan prefer a national park or a theme park?",
        expansion_reason="outdoor_preference_bridge",
        text=(
            "D10:12 Morgan: We always look forward to our family camping trip. "
            "We roast marshmallows around the campfire; it is the highlight "
            "of our summer."
        ),
    )
    assert source_sibling_answer_evidence(
        expansion_query="Would Morgan prefer a national park or a theme park?",
        expansion_reason="outdoor_nature_memory_bridge",
        text=(
            "D10:14 Morgan: I'll always remember the camping trip when we saw "
            "a meteor shower and felt at one with the universe."
        ),
    )


def test_source_sibling_answer_evidence_accepts_children_preference_turns() -> None:
    assert source_sibling_answer_evidence(
        expansion_query="What do Avery's kids like?",
        expansion_reason="children_preference_bridge",
        text=(
            "D6:6 Avery: They were stoked for the dinosaur exhibit. "
            "They love learning about animals and the bones were cool."
        ),
    )
    assert source_sibling_answer_evidence(
        expansion_query="What do Avery's children like?",
        expansion_reason="children_preference_bridge",
        text=(
            "D4:8 Avery: The younger kids love nature, campfires, and "
            "hiking outdoors."
        ),
    )


def test_source_sibling_answer_evidence_rejects_temporal_query_without_time_signal() -> None:
    assert not source_sibling_answer_evidence(
        expansion_query="When did Melanie go to the museum?",
        expansion_reason="original_query",
        text="D6:4 Melanie: I took the kids to the museum and they enjoyed it.",
    )


def test_distant_source_sibling_rank_accepts_generic_list_slot_evidence() -> None:
    seed = _chunk(
        chunk_id="seed",
        source_external_id="locomo:conv-41:session_20:D20:10:turn",
        sequence=10,
        text="D20:10: John: Family keeps showing up for me.",
    )
    distant_evidence = _chunk(
        chunk_id="evidence",
        source_external_id="locomo:conv-41:session_20:D20:4:turn",
        sequence=4,
        text=(
            "D20:4: Maria: Last week, we had a blast at a live music event. "
            "Seeing them enjoy the songs made the night special."
        ),
    )

    rank = source_sibling_distant_answer_evidence_rank(
        distant_evidence,
        source_groups=source_group_seed_turns((seed,)),
        expansion_query="What music events has John attended?",
        expansion_reason="music_event_inventory_bridge",
        text=distant_evidence.text,
    )

    assert rank is not None
    assert rank.turn_delta == -6
    assert rank.turn_distance == 5


def test_distant_source_sibling_rank_accepts_lgbtq_community_participation_slot() -> None:
    seed = _chunk(
        chunk_id="seed",
        source_external_id="locomo:generic:session_9:D9:2:turn",
        sequence=2,
        text=(
            "D9:2 Riley: I joined an LGBTQ mentorship program to help younger "
            "people feel supported."
        ),
    )
    distant_evidence = _chunk(
        chunk_id="distant",
        source_external_id="locomo:generic:session_9:D9:12:turn",
        sequence=12,
        text=(
            "D9:12 Riley: Next month I am organizing an LGBTQ art show with "
            "paintings about community pride."
        ),
    )

    rank = source_sibling_distant_answer_evidence_rank(
        distant_evidence,
        source_groups=source_group_seed_turns((seed,)),
        expansion_query="In what ways is Riley participating in the LGBTQ community?",
        expansion_reason="lgbtq_community_participation_bridge",
        text=distant_evidence.text,
    )

    assert rank is not None
    assert rank.turn_delta == 10
    assert rank.turn_distance == 5


def test_source_sibling_candidate_limit_covers_many_seed_groups() -> None:
    assert source_sibling_candidate_limit(max_items=32, source_group_count=20) == 640
    assert source_sibling_candidate_limit(max_items=100, source_group_count=100) == 1024
    assert source_sibling_candidate_limit(max_items=0, source_group_count=20) == 0


def test_source_sibling_relevance_gate_accepts_generic_list_slot_evidence() -> None:
    seed = _chunk(
        chunk_id="seed",
        source_external_id="locomo:conv-41:session_24:D24:7:turn",
        sequence=7,
        text="D24:7: John: I was thinking about service.",
    )
    evidence = _chunk(
        chunk_id="evidence",
        source_external_id="locomo:conv-41:session_24:D24:1:turn",
        sequence=1,
        text=(
            "D24:1: John: I visited a veteran's hospital and met some amazing "
            "people. It made me appreciate the need to give back."
        ),
    )
    rank = source_sibling_distant_answer_evidence_rank(
        evidence,
        source_groups=source_group_seed_turns((seed,)),
        expansion_query="What events for veterans has John participated in?",
        expansion_reason="veterans_event_inventory_bridge",
        text=evidence.text,
    )

    assert rank is not None
    assert source_sibling_relevance_allowed(
        rank=rank,
        relevance=QueryRelevance(
            score_boost=0.0,
            query_term_count=8,
            unique_term_hits=0,
            capped_frequency_hits=0,
            hit_ratio=0.0,
            distinctive_term_count=4,
            distinctive_term_hits=0,
        ),
        expansion_query="What events for veterans has John participated in?",
        expansion_reason="veterans_event_inventory_bridge",
        text=evidence.text,
    )


def _chunk(
    *,
    chunk_id: str,
    source_external_id: str,
    sequence: int,
    text: str,
) -> MemoryChunk:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return MemoryChunk(
        id=chunk_id,
        space_id="space",
        memory_scope_id="scope",
        thread_id="thread",
        document_id="document",
        episode_id=None,
        source_type="locomo_turn",
        source_external_id=source_external_id,
        source_hash=f"hash-{chunk_id}",
        kind=MemoryChunkKind.DOCUMENT_SECTION,
        text=text,
        normalized_text=text.casefold(),
        status=LifecycleStatus.ACTIVE,
        sequence=sequence,
        char_start=0,
        char_end=len(text),
        token_estimate=24,
        created_at=now,
        updated_at=now,
        metadata={},
    )
