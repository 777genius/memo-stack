from infinity_context_core.application.context_causal_reason_rerank import (
    causal_reason_rerank_signal,
)
from infinity_context_core.application.context_domain_rerank_signals import (
    age_birthday_rerank_signal,
    aggregation_evidence_rerank_signal,
    birthplace_rerank_signal,
    commonality_rerank_signal,
    current_goal_rerank_signal,
    current_state_rerank_signal,
    event_sequence_rerank_signal,
    family_hike_detail_rerank_signal,
    inventory_list_rerank_signal,
    positive_preference_rerank_signal,
    relationship_duration_rerank_signal,
    relationship_status_rerank_signal,
    state_transition_rerank_signal,
    support_network_rerank_signal,
)
from infinity_context_core.application.context_relevance import QueryRelevance
from infinity_context_core.application.dto import ContextItem
from infinity_context_core.domain.entities import SourceRef


def test_support_network_signal_prefers_social_support_over_technical_noise() -> None:
    exact = _item(
        "exact",
        text="Caroline's mother and coach were there for her and comforted her.",
        query_expansion_reason="support_network_bridge",
    )
    weak = _item(
        "weak",
        text="Caroline wrote technical support notes for the SDK runtime.",
        query_expansion_reason="support_network_bridge",
    )

    exact_signal = support_network_rerank_signal(
        query_reason="support_network_bridge",
        item=exact,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )
    weak_signal = support_network_rerank_signal(
        query_reason="support_network_bridge",
        item=weak,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )

    assert exact_signal.boost > 0
    assert exact_signal.reason == "support_network_exact_evidence"
    assert weak_signal.penalty > 0
    assert weak_signal.reason == "support_network_weak_evidence"


def test_support_network_signal_accepts_negative_experience_support_bridge() -> None:
    exact = _item(
        "negative_experience_support",
        text=(
            "Caroline's friends, family, and mentors are her rocks and give "
            "her strength after a hard experience."
        ),
        query_expansion_reason="negative_experience_support_bridge",
    )

    signal = support_network_rerank_signal(
        query_reason="negative_experience_support_bridge",
        item=exact,
        relevance=_relevance(distinctive_term_hits=6, unique_term_hits=6),
    )

    assert signal.boost > 0
    assert signal.reason == "support_network_exact_evidence"


def test_inventory_signal_requires_query_specific_exact_slot() -> None:
    pottery = _item(
        "pottery",
        text="Melanie and the kids made clay bowls and a small cup.",
        query_expansion_reason="decomposition_inventory_list",
    )
    country_noise = _item(
        "country_noise",
        text="Melanie visited Spain and talked about countries abroad.",
        query_expansion_reason="decomposition_inventory_list",
    )

    pottery_signal = inventory_list_rerank_signal(
        query="What types of pottery have Melanie and her kids made?",
        query_reason="decomposition_inventory_list",
        item=pottery,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )
    noise_signal = inventory_list_rerank_signal(
        query="What types of pottery have Melanie and her kids made?",
        query_reason="decomposition_inventory_list",
        item=country_noise,
        relevance=_relevance(distinctive_term_hits=1, unique_term_hits=2),
    )

    assert pottery_signal.boost > 0
    assert pottery_signal.reason == "inventory_list_exact_evidence"
    assert noise_signal.penalty > 0
    assert noise_signal.reason == "inventory_list_weak_evidence"


def test_event_sequence_signal_requires_exact_event_anchors_and_outcome() -> None:
    exact = _item(
        "sam_atlas",
        text=(
            "After talking with Sam about Atlas, Alex decided to wait for "
            "invoice approval before launch."
        ),
        query_expansion_reason="decomposition_event_sequence",
    )
    wrong_thread = _item(
        "priya_stripe",
        text="After talking with Priya about Stripe, Alex changed the retry plan.",
        query_expansion_reason="decomposition_event_sequence",
    )

    exact_signal = event_sequence_rerank_signal(
        query="What did Alex decide after talking with Sam about Atlas?",
        query_reason="decomposition_event_sequence",
        item=exact,
        relevance=_relevance(distinctive_term_hits=4, unique_term_hits=4),
    )
    weak_signal = event_sequence_rerank_signal(
        query="What did Alex decide after talking with Sam about Atlas?",
        query_reason="conversation_transcript_evidence_bridge",
        item=wrong_thread,
        relevance=_relevance(distinctive_term_hits=3, unique_term_hits=3),
    )

    assert exact_signal.boost > 0
    assert exact_signal.reason == "event_sequence_exact_evidence"
    assert weak_signal.penalty > 0
    assert weak_signal.reason == "event_sequence_anchor_mismatch"


def test_current_goal_signal_prefers_goal_evidence_over_weak_decoy() -> None:
    exact = _item(
        "adoption_goal",
        text=(
            "Caroline hopes to build her own family. Adoption is her current "
            "goal and next step."
        ),
        query_expansion_reason="adoption_current_goal_bridge",
    )
    weak = _item(
        "home_country_decoy",
        text="Caroline misses her home country sometimes and may move back someday.",
        query_expansion_reason="adoption_current_goal_bridge",
    )

    exact_signal = current_goal_rerank_signal(
        query_reason="adoption_current_goal_bridge",
        item=exact,
        relevance=_relevance(distinctive_term_hits=7, unique_term_hits=7),
    )
    weak_signal = current_goal_rerank_signal(
        query_reason="adoption_current_goal_bridge",
        item=weak,
        relevance=_relevance(distinctive_term_hits=2, unique_term_hits=2),
    )

    assert exact_signal.boost > 0
    assert exact_signal.reason == "current_goal_exact_evidence"
    assert weak_signal.penalty > 0
    assert weak_signal.reason == "current_goal_weak_evidence"


def test_positive_preference_signal_prefers_explicit_preference_over_topic_mention() -> None:
    exact = _item(
        "roasted_chicken",
        text="Audrey says roasted chicken is one of her favorite comfort meals.",
        query_expansion_reason="food_preference_bridge",
    )
    topical = _item(
        "chicken_recipe",
        text="Audrey cooked chicken with lemon for the fundraiser.",
        query_expansion_reason="food_preference_bridge",
    )

    exact_signal = positive_preference_rerank_signal(
        query="Which meat does Audrey prefer eating more than others?",
        query_reason="food_preference_bridge",
        item=exact,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )
    topical_signal = positive_preference_rerank_signal(
        query="Which meat does Audrey prefer eating more than others?",
        query_reason="food_preference_bridge",
        item=topical,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )

    assert exact_signal.boost > 0
    assert exact_signal.reason == "preference_exact_evidence"
    assert topical_signal.penalty > 0
    assert topical_signal.reason == "preference_weak_evidence"


def test_positive_preference_signal_prefers_outdoor_nature_evidence() -> None:
    exact = _item(
        "perseid_trip",
        text=(
            "Melanie remembered the camping trip where her family watched the Perseid "
            "meteor shower and felt at one with the universe."
        ),
        query_expansion_reason="outdoor_preference_bridge",
    )
    topical = _item(
        "generic_park",
        text="Melanie took her kids to a park and saw them play outside.",
        query_expansion_reason="outdoor_preference_bridge",
    )

    exact_signal = positive_preference_rerank_signal(
        query="Would Melanie be more interested in a national park or a theme park?",
        query_reason="outdoor_preference_bridge",
        item=exact,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=6),
    )
    topical_signal = positive_preference_rerank_signal(
        query="Would Melanie be more interested in a national park or a theme park?",
        query_reason="outdoor_preference_bridge",
        item=topical,
        relevance=_relevance(distinctive_term_hits=4, unique_term_hits=4),
    )

    assert exact_signal.boost > 0
    assert exact_signal.reason == "outdoor_preference_exact_evidence"
    assert topical_signal.penalty > 0
    assert topical_signal.reason == "preference_weak_evidence"


def test_causal_reason_signal_prefers_reason_evidence_over_topical_decoy() -> None:
    exact = _item(
        "gina_job_loss",
        text=(
            "Gina lost her Door Dash job, so she started thinking seriously "
            "about opening her own clothing store."
        ),
        query_expansion_reason="business_start_reason_bridge",
    )
    topical = _item(
        "gina_store_topic",
        text="Gina mentioned her clothing store during a planning update.",
        query_expansion_reason="business_start_reason_bridge",
    )

    exact_signal = causal_reason_rerank_signal(
        query="Why did Gina start her own clothing store?",
        query_reason="business_start_reason_bridge",
        item=exact,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )
    topical_signal = causal_reason_rerank_signal(
        query="Why did Gina start her own clothing store?",
        query_reason="business_start_reason_bridge",
        item=topical,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )

    assert exact_signal.boost > 0
    assert exact_signal.reason == "causal_reason_exact_evidence"
    assert topical_signal.penalty > 0
    assert topical_signal.reason == "causal_reason_weak_evidence"


def test_commonality_signal_requires_both_query_anchors_and_shared_shape() -> None:
    exact = _item(
        "shared_hobbies",
        text="Caroline and Melanie both enjoy painting and weekend camping.",
        query_expansion_reason="commonality_interest_bridge",
    )
    weak = _item(
        "shared_photo",
        text="Caroline shared a photo of a painting with Melanie.",
        query_expansion_reason="commonality_interest_bridge",
    )

    exact_signal = commonality_rerank_signal(
        query="What hobbies do Caroline and Melanie have in common?",
        query_reason="commonality_interest_bridge",
        item=exact,
        relevance=_relevance(distinctive_term_hits=8, unique_term_hits=8),
    )
    weak_signal = commonality_rerank_signal(
        query="What hobbies do Caroline and Melanie have in common?",
        query_reason="commonality_interest_bridge",
        item=weak,
        relevance=_relevance(distinctive_term_hits=4, unique_term_hits=5),
    )

    assert exact_signal.boost > 0
    assert exact_signal.reason == "commonality_exact_evidence"
    assert weak_signal.penalty > 0
    assert weak_signal.reason == "commonality_weak_evidence"


def test_commonality_signal_allows_shared_painted_subject_single_anchor_evidence() -> None:
    exact = _item(
        "caroline_sunset_painting",
        text="D14:5 Caroline finished a new work. visual query: sunset painting.",
        query_expansion_reason="shared_painted_subject_bridge",
    )
    topic_only = _item(
        "generic_shared_painting",
        text="Caroline and Melanie both enjoy painting on weekends.",
        query_expansion_reason="shared_painted_subject_bridge",
    )

    exact_signal = commonality_rerank_signal(
        query="What subject have Caroline and Melanie both painted?",
        query_reason="shared_painted_subject_bridge",
        item=exact,
        relevance=_relevance(distinctive_term_hits=7, unique_term_hits=7),
    )
    topic_signal = commonality_rerank_signal(
        query="What subject have Caroline and Melanie both painted?",
        query_reason="shared_painted_subject_bridge",
        item=topic_only,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )

    assert exact_signal.boost > 0
    assert exact_signal.reason == "shared_painted_subject_exact_evidence"
    assert topic_signal.penalty > 0
    assert topic_signal.reason == "shared_painted_subject_topic_only_noise"


def test_family_hike_detail_signal_prefers_campfire_actions_over_topic_only() -> None:
    exact = _item(
        "campfire_actions",
        text=(
            "Melanie roasted marshmallows and shared stories around the "
            "campfire with her family."
        ),
        query_expansion_reason="family_hike_detail_bridge",
    )
    topic_only = _item(
        "hike_photo",
        text="Melanie hikes with her kids and takes nature photos near a trail.",
        query_expansion_reason="family_hike_activity_bridge",
    )

    exact_signal = family_hike_detail_rerank_signal(
        query_reason="family_hike_detail_bridge",
        item=exact,
        relevance=_relevance(distinctive_term_hits=8, unique_term_hits=8),
    )
    topic_signal = family_hike_detail_rerank_signal(
        query_reason="family_hike_activity_bridge",
        item=topic_only,
        relevance=_relevance(distinctive_term_hits=6, unique_term_hits=6),
    )

    assert exact_signal.boost > 0
    assert exact_signal.reason == "family_hike_detail_exact_evidence"
    assert topic_signal.penalty > 0
    assert topic_signal.reason == "family_hike_detail_topic_only_noise"


def test_commonality_signal_boosts_who_else_single_anchor_answer() -> None:
    also_person = _item(
        "maria_also_camping",
        text="Maria also likes camping and hiking on weekends.",
        query_expansion_reason="commonality_interest_bridge",
    )

    signal = commonality_rerank_signal(
        query="Who else likes camping like Caroline?",
        query_reason="commonality_interest_bridge",
        item=also_person,
        relevance=_relevance(distinctive_term_hits=6, unique_term_hits=6),
    )

    assert signal.boost > 0
    assert signal.reason == "commonality_who_else_evidence"


def test_commonality_signal_penalizes_original_person_for_who_else_query() -> None:
    original_person = _item(
        "caroline_camping",
        text="Caroline likes camping on weekends.",
        query_expansion_reason="commonality_interest_bridge",
    )

    signal = commonality_rerank_signal(
        query="Who else likes camping like Caroline?",
        query_reason="commonality_interest_bridge",
        item=original_person,
        relevance=_relevance(distinctive_term_hits=6, unique_term_hits=6),
    )

    assert signal.penalty > 0
    assert signal.reason == "commonality_original_person_noise"


def test_aggregation_signal_prefers_multi_evidence_count_context() -> None:
    aggregation = _item(
        "beach_aggregation",
        text=(
            "D1:2 Melanie went to the beach in March. D4:7 Melanie went to the "
            "beach again in July. D8:3 She visited the beach one more time."
        ),
        query_expansion_reason="beach_count_activity_bridge",
        retrieval_source="keyword_aggregation_chunks",
        source_ref_count=3,
    )
    single = _item(
        "single_beach",
        text="Melanie went to the beach recently and the kids had a blast.",
        query_expansion_reason="beach_count_activity_bridge",
    )

    exact_signal = aggregation_evidence_rerank_signal(
        query="How many times has Melanie gone to the beach in 2023?",
        item=aggregation,
    )
    weak_signal = aggregation_evidence_rerank_signal(
        query="How many times has Melanie gone to the beach in 2023?",
        item=single,
    )

    assert exact_signal.boost > 0
    assert exact_signal.reason == "aggregation_multi_evidence"
    assert weak_signal.penalty > 0
    assert weak_signal.reason == "aggregation_single_evidence_noise"


def test_aggregation_signal_prefers_multi_evidence_list_context() -> None:
    aggregation = _item(
        "shelter_aggregation",
        text=(
            "D2:1 Maria volunteers at the homeless shelter. "
            "D11:10 Maria also started volunteering at the dog shelter."
        ),
        query_expansion_reason="decomposition_inventory_list",
        retrieval_source="keyword_aggregation_chunks",
        source_ref_count=2,
    )
    single = _item(
        "single_shelter",
        text="D2:1 Maria volunteers at the homeless shelter every weekend.",
        query_expansion_reason="decomposition_inventory_list",
    )

    exact_signal = aggregation_evidence_rerank_signal(
        query="What shelters does Maria volunteer at?",
        item=aggregation,
        has_multi_evidence_competitor=True,
    )
    incomplete_signal = aggregation_evidence_rerank_signal(
        query="What shelters does Maria volunteer at?",
        item=single,
        has_multi_evidence_competitor=True,
    )
    unopposed_signal = aggregation_evidence_rerank_signal(
        query="What shelters does Maria volunteer at?",
        item=single,
    )

    assert exact_signal.boost > 0
    assert exact_signal.reason == "aggregation_list_multi_evidence"
    assert incomplete_signal.penalty > 0
    assert incomplete_signal.reason == "aggregation_list_single_evidence_incomplete"
    assert unopposed_signal == type(unopposed_signal)()


def test_aggregation_signal_keeps_single_multi_value_list_evidence() -> None:
    direct_list = _item(
        "direct_shelter_list",
        text=(
            "Maria volunteers at the homeless shelter and also helps at the dog shelter."
        ),
        query_expansion_reason="decomposition_inventory_list",
    )

    signal = aggregation_evidence_rerank_signal(
        query="What shelters does Maria volunteer at?",
        item=direct_list,
        has_multi_evidence_competitor=True,
    )

    assert signal == type(signal)()


def test_aggregation_signal_keeps_direct_numeric_count_answer() -> None:
    direct_count = _item(
        "children_count",
        text="Melanie has three children.",
        query_expansion_reason="children_count_event_bridge",
    )

    signal = aggregation_evidence_rerank_signal(
        query="How many children does Melanie have?",
        item=direct_count,
    )

    assert signal == type(signal)()


def test_relationship_status_signal_prefers_status_over_social_decoy() -> None:
    exact = _item(
        "single_parent",
        text="Caroline is single and described herself as a single parent.",
        query_expansion_reason="relationship_status_bridge",
    )
    decoy = _item(
        "old_friend",
        text="Caroline's old friend from school is Maria.",
        query_expansion_reason="relationship_status_bridge",
    )
    work_partner = _item(
        "work_partner",
        text="Caroline's project partner on Atlas is Maria.",
        query_expansion_reason="relationship_status_bridge",
    )

    exact_signal = relationship_status_rerank_signal(
        query_reason="relationship_status_bridge",
        item=exact,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )
    decoy_signal = relationship_status_rerank_signal(
        query_reason="relationship_status_bridge",
        item=decoy,
        relevance=_relevance(distinctive_term_hits=3, unique_term_hits=4),
    )
    work_signal = relationship_status_rerank_signal(
        query_reason="relationship_status_bridge",
        item=work_partner,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )

    assert exact_signal.boost > 0
    assert exact_signal.reason == "relationship_status_exact_evidence"
    assert decoy_signal.penalty > 0
    assert decoy_signal.reason == "relationship_status_weak_evidence"
    assert work_signal.penalty > 0
    assert work_signal.reason == "relationship_status_weak_evidence"


def test_relationship_status_signal_penalizes_non_romantic_partner_contexts() -> None:
    cases = (
        "Alex is Caroline's accountability partner for marathon training.",
        "Maria is Caroline's study partner in the evening class.",
        "John is Caroline's research partner in the lab.",
    )

    for text in cases:
        signal = relationship_status_rerank_signal(
            query_reason="relationship_status_bridge",
            item=_item(
                "non_romantic_partner",
                text=text,
                query_expansion_reason="relationship_status_bridge",
            ),
            relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
        )

        assert signal.penalty > 0
        assert signal.reason == "relationship_status_weak_evidence"


def test_relationship_duration_signal_prefers_duration_over_generic_relation() -> None:
    exact = _item(
        "known_for_years",
        text="Alex and Maria have known each other for seven years.",
        query_expansion_reason="relationship_duration_bridge",
    )
    generic = _item(
        "old_friend",
        text="Alex's old friend from school is Maria.",
        query_expansion_reason="relationship_duration_bridge",
    )

    exact_signal = relationship_duration_rerank_signal(
        query_reason="relationship_duration_bridge",
        item=exact,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )
    generic_signal = relationship_duration_rerank_signal(
        query_reason="relationship_duration_bridge",
        item=generic,
        relevance=_relevance(distinctive_term_hits=3, unique_term_hits=4),
    )

    assert exact_signal.boost > 0
    assert exact_signal.reason == "relationship_duration_exact_evidence"
    assert generic_signal.penalty > 0
    assert generic_signal.reason == "relationship_duration_weak_evidence"


def test_state_transition_signal_prefers_explicit_transition_pair_over_topic_note() -> None:
    exact = _item(
        "provider_transition",
        text="After the Atlas call, Atlas changed from LocalAI to OpenAI.",
        query_expansion_reason="change_over_time_bridge",
    )
    weak = _item(
        "topic_note",
        text="After the Atlas call, Alex reviewed provider notes for the launch.",
        query_expansion_reason="change_over_time_bridge",
    )

    exact_signal = state_transition_rerank_signal(
        query_reason="change_over_time_bridge",
        item=exact,
        relevance=_relevance(distinctive_term_hits=6, unique_term_hits=7),
    )
    weak_signal = state_transition_rerank_signal(
        query_reason="change_over_time_bridge",
        item=weak,
        relevance=_relevance(distinctive_term_hits=3, unique_term_hits=4),
    )

    assert exact_signal.boost > 0
    assert exact_signal.reason == "state_transition_exact_evidence"
    assert weak_signal.penalty > 0
    assert weak_signal.reason == "state_transition_weak_evidence"


def test_current_state_signal_prefers_active_state_over_stale_text() -> None:
    active = _item(
        "active_provider",
        text="Atlas provider remains valid and active: OpenAI.",
        query_expansion_reason="current_state_temporal_bridge",
    )
    stale = _item(
        "stale_provider",
        text="LocalAI is no longer valid for Atlas after the provider switch.",
        query_expansion_reason="current_state_temporal_bridge",
    )

    active_signal = current_state_rerank_signal(
        query="Which Atlas provider is still valid?",
        query_reason="current_state_temporal_bridge",
        item=active,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )
    stale_signal = current_state_rerank_signal(
        query="Which Atlas provider is still valid?",
        query_reason="current_state_temporal_bridge",
        item=stale,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )

    assert active_signal.boost > 0
    assert active_signal.reason == "current_state_exact_evidence"
    assert stale_signal.penalty > 0
    assert stale_signal.reason == "current_state_stale_conflict"


def test_current_state_signal_prefers_stale_evidence_for_no_longer_query() -> None:
    stale = _item(
        "stale_provider",
        text="LocalAI is no longer valid because it was superseded by OpenAI.",
        query_expansion_reason="stale_state_temporal_bridge",
    )
    active = _item(
        "active_provider",
        text="OpenAI is the selected current Atlas provider.",
        query_expansion_reason="stale_state_temporal_bridge",
    )

    stale_signal = current_state_rerank_signal(
        query="Which Atlas provider is no longer valid?",
        query_reason="stale_state_temporal_bridge",
        item=stale,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )
    active_signal = current_state_rerank_signal(
        query="Which Atlas provider is no longer valid?",
        query_reason="stale_state_temporal_bridge",
        item=active,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )

    assert stale_signal.boost > 0
    assert stale_signal.reason == "stale_state_exact_evidence"
    assert active_signal.penalty > 0
    assert active_signal.reason == "stale_state_current_conflict"


def test_current_state_signal_does_not_treat_previous_conversation_as_stale_state() -> None:
    signal = current_state_rerank_signal(
        query="What did Alex say in the previous conversation?",
        query_reason="original_query",
        item=_item(
            "active_provider",
            text="Atlas final decision: OpenAI is the selected current provider.",
            query_expansion_reason="original_query",
        ),
        relevance=_relevance(distinctive_term_hits=4, unique_term_hits=4),
    )

    assert signal == type(signal)()


def test_age_birthday_signal_prefers_birth_evidence_over_old_word_noise() -> None:
    exact = _item(
        "birth_year",
        text="Alex was born in 1992 and his birthday is in June.",
        query_expansion_reason="age_birthday_bridge",
    )
    weak = _item(
        "old_friend",
        text="Alex's old friend from school is Maria.",
        query_expansion_reason="age_birthday_bridge",
    )

    exact_signal = age_birthday_rerank_signal(
        query_reason="age_birthday_bridge",
        item=exact,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )
    weak_signal = age_birthday_rerank_signal(
        query_reason="age_birthday_bridge",
        item=weak,
        relevance=_relevance(distinctive_term_hits=3, unique_term_hits=4),
    )

    assert exact_signal.boost > 0
    assert exact_signal.reason == "age_birthday_exact_evidence"
    assert weak_signal.penalty > 0
    assert weak_signal.reason == "age_birthday_weak_evidence"


def test_age_birthday_signal_penalizes_birthdate_for_birthplace_query() -> None:
    birthdate = _item(
        "birth_year",
        text="Alex was born in 1992 and his birthday is in June.",
        query_expansion_reason="age_birthday_bridge",
    )

    signal = age_birthday_rerank_signal(
        query="Where was Alex born?",
        query_reason="age_birthday_bridge",
        item=birthdate,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )

    assert signal.penalty > 0
    assert signal.reason == "age_birthday_birthplace_query_noise"


def test_birthplace_signal_prefers_place_over_birthdate_noise() -> None:
    exact = _item(
        "birthplace",
        text="Alex was born in Sweden, his home country, before moving abroad.",
        query_expansion_reason="birthplace_origin_bridge",
    )
    birthdate_noise = _item(
        "birth_year",
        text="Alex was born in 1992 and his birthday is in June.",
        query_expansion_reason="birthplace_origin_bridge",
    )

    exact_signal = birthplace_rerank_signal(
        query_reason="birthplace_origin_bridge",
        item=exact,
        relevance=_relevance(distinctive_term_hits=5, unique_term_hits=5),
    )
    noise_signal = birthplace_rerank_signal(
        query_reason="birthplace_origin_bridge",
        item=birthdate_noise,
        relevance=_relevance(distinctive_term_hits=4, unique_term_hits=5),
    )

    assert exact_signal.boost > 0
    assert exact_signal.reason == "birthplace_exact_evidence"
    assert noise_signal.penalty > 0
    assert noise_signal.reason == "birthplace_birthdate_noise"


def _item(
    item_id: str,
    *,
    text: str,
    query_expansion_reason: str,
    retrieval_source: str = "keyword_chunks",
    source_ref_count: int = 1,
) -> ContextItem:
    return ContextItem(
        item_id=item_id,
        item_type="chunk",
        text=text,
        score=0.7,
        source_refs=tuple(
            SourceRef(source_type="document", source_id=f"doc-{index}")
            for index in range(source_ref_count)
        ),
        diagnostics={
            "retrieval_source": retrieval_source,
            "retrieval_sources": [retrieval_source],
            "score_signals": {"query_expansion_reason": query_expansion_reason},
        },
    )


def _relevance(*, distinctive_term_hits: int, unique_term_hits: int) -> QueryRelevance:
    return QueryRelevance(
        score_boost=0.0,
        query_term_count=5,
        unique_term_hits=unique_term_hits,
        capped_frequency_hits=unique_term_hits,
        hit_ratio=0.0,
        distinctive_term_count=5,
        distinctive_term_hits=distinctive_term_hits,
    )
