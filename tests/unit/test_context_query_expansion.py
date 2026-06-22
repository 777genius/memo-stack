from infinity_context_core.application.context_query_expansion import (
    QueryExpansionPlan,
    build_query_expansion_plan,
)
from infinity_context_core.application.context_ranking import (
    best_query_relevance,
    keyword_chunk_score,
)
from infinity_context_core.application.context_relevance import score_query_relevance


def test_query_expansion_preserves_identity_for_relocation_bridge() -> None:
    plan = build_query_expansion_plan("Where did Caroline move from 4 years ago?")

    assert plan.retrieval_queries[0].reason == "original_query"
    relocation = _expansion_query(plan, "relocation_origin_bridge")
    assert relocation.startswith("Caroline ")
    assert "home country roots" in relocation


def test_query_expansion_covers_low_overlap_ally_and_outdoor_questions() -> None:
    ally = build_query_expansion_plan(
        "Would Melanie be considered an ally to the transgender community?"
    )
    outdoor = build_query_expansion_plan(
        "Would Melanie be more interested in going to a national park or a theme park?"
    )

    assert _expansion_query(ally, "ally_support_bridge").startswith("Melanie ")
    assert "supportive support acceptance" in _expansion_query(
        ally,
        "ally_support_bridge",
    )
    assert _expansion_query(outdoor, "outdoor_preference_bridge").startswith(
        "Melanie "
    )
    assert "camping trip campfire meteor shower" in _expansion_query(
        outdoor,
        "outdoor_preference_bridge",
    )
    assert "meteor shower sky universe" in _expansion_query(
        outdoor,
        "outdoor_nature_memory_bridge",
    )


def test_query_expansion_is_bounded_and_deduplicated_by_reason() -> None:
    plan = build_query_expansion_plan(
        "Would Melanie support growing up, move from home, choose a national park "
        "or theme park, make a decision to adopt, be an ally to the transgender "
        "community, have political leaning, be religious, and destress?"
    )

    reasons = [expansion.reason for expansion in plan.expansions]
    assert len(plan.expansions) <= 8
    assert len(reasons) == len(set(reasons))
    assert reasons.count("outdoor_preference_bridge") == 1
    assert reasons.count("outdoor_nature_memory_bridge") <= 1


def test_query_expansion_covers_activity_location_and_destress_bridges() -> None:
    camped = build_query_expansion_plan("Where has Melanie camped?")
    activities = build_query_expansion_plan("What activities does Melanie partake in?")
    destress = build_query_expansion_plan("What does Melanie do to destress?")

    assert "mountains beach forest" in _expansion_query(
        camped,
        "camping_location_bridge",
    )
    assert "pottery camping painting swimming" in _expansion_query(
        activities,
        "activity_aggregation_bridge",
    )
    assert "running pottery class therapeutic" in _expansion_query(
        destress,
        "destress_activity_bridge",
    )


def test_query_expansion_covers_event_participation_bridges() -> None:
    events = build_query_expansion_plan(
        "What LGBTQ+ events has Caroline participated in?"
    )
    helping = build_query_expansion_plan(
        "What events has Caroline participated in to help children?"
    )

    assert "events participated attended joined went" in _expansion_query(
        events,
        "event_participation_bridge",
    )
    assert "mentorship mentoring program youth" in _expansion_query(
        events,
        "event_participation_bridge",
    )
    assert "pride parade marched flags" in _expansion_query(
        events,
        "lgbtq_pride_event_bridge",
    )
    assert "support group transgender stories" in _expansion_query(
        events,
        "lgbtq_support_group_event_bridge",
    )
    assert "school event speech talk" in _expansion_query(
        events,
        "lgbtq_school_event_bridge",
    )
    assert "transgender_poetry_event_bridge" not in {
        expansion.reason for expansion in events.expansions
    }
    assert "help children youth mentorship" in _expansion_query(
        helping,
        "event_participation_help_bridge",
    )
    assert "activist group connected activists" in _expansion_query(
        build_query_expansion_plan(
            "In what ways is Caroline participating in the LGBTQ community?"
        ),
        "lgbtq_community_participation_bridge",
    )


def test_query_expansion_covers_locomo_inference_bridges() -> None:
    workshop = build_query_expansion_plan(
        "What kind of counseling workshop did Melanie attend recently?"
    )
    degree = build_query_expansion_plan("What might John's degree be in?")
    friends = build_query_expansion_plan(
        "Is it likely that Nate has friends besides Joanna?"
    )

    assert "therapeutic methods trans people" in _expansion_query(
        workshop,
        "counseling_workshop_bridge",
    )
    assert "policymaking policy political science" in _expansion_query(
        degree,
        "degree_policy_inference_bridge",
    )
    assert "teammates team video game" in _expansion_query(
        friends,
        "friends_team_inference_bridge",
    )


def test_query_expansion_covers_locomo_reliable_failure_bridges() -> None:
    cases = [
        (
            build_query_expansion_plan(
                "What activities has Melanie done with her family?"
            ),
            "family_activity_bridge",
            "kids children husband museum",
        ),
        (
            build_query_expansion_plan(
                "What activities has Melanie done with her family?"
            ),
            "family_painting_activity_bridge",
            "painting together nature inspired",
        ),
        (
            build_query_expansion_plan(
                "What activities has Melanie done with her family?"
            ),
            "family_swimming_activity_bridge",
            "swimming with kids swim",
        ),
        (
            build_query_expansion_plan(
                "What activities has Melanie done with her family?"
            ),
            "family_motivation_context_bridge",
            "husband kids children keep motivated",
        ),
        (
            build_query_expansion_plan(
                "Does John live close to a beach or the mountains?"
            ),
            "beach_or_mountains_inference_bridge",
            "beach ocean sunset sailboat",
        ),
        (
            build_query_expansion_plan("What job might Maria pursue in the future?"),
            "volunteer_career_inference_bridge",
            "volunteering volunteer shelter",
        ),
        (
            build_query_expansion_plan(
                "What fields would Caroline be likely to pursue in her educaton?"
            ),
            "education_career_field_bridge",
            "career options fields jobs counseling",
        ),
        (
            build_query_expansion_plan("What is Caroline's identity?"),
            "identity_bridge",
            "transgender trans woman transition",
        ),
        (
            build_query_expansion_plan("What is Caroline's relationship status?"),
            "relationship_status_bridge",
            "single parent breakup partner married",
        ),
        (
            build_query_expansion_plan(
                "What pets would not cause any discomfort to Joanna?"
            ),
            "pet_allergy_discomfort_bridge",
            "reptiles fur allergic",
        ),
        (
            build_query_expansion_plan(
                "What underlying condition might Joanna have based on her allergies?"
            ),
            "allergy_condition_inference_bridge",
            "allergies allergic reptiles",
        ),
        (
            build_query_expansion_plan("What symbols are important to Caroline?"),
            "symbol_importance_bridge",
            "rainbow flag mural eagle",
        ),
        (
            build_query_expansion_plan("What Console does Nate own?"),
            "console_game_cover_bridge",
            "console nintendo game cover",
        ),
        (
            build_query_expansion_plan(
                "What musical artists/bands has Melanie seen?"
            ),
            "music_artist_band_bridge",
            "summer sounds band pop song",
        ),
        (
            build_query_expansion_plan(
                "What are the new shoes that Caroline got used for?"
            ),
            "shoe_usage_bridge",
            "purple walking running",
        ),
        (
            build_query_expansion_plan(
                "How did Caroline feel while watching the meteor shower?"
            ),
            "meteor_shower_feeling_bridge",
            "felt tiny awe universe",
        ),
        (
            build_query_expansion_plan(
                "Why did Caroline choose to use colors and patterns in her "
                "pottery project?"
            ),
            "pottery_color_reason_bridge",
            "catch eye make people smile",
        ),
        (
            build_query_expansion_plan(
                "What transgender-specific events has Caroline attended?"
            ),
            "transgender_poetry_event_bridge",
            "transgender event poetry reading",
        ),
        (
            build_query_expansion_plan(
                "What book did Melanie read from Caroline's suggestion?"
            ),
            "book_suggestion_bridge",
            "becoming nicole amy ellis nutt",
        ),
        (
            build_query_expansion_plan("How many children does Melanie have?"),
            "children_count_sibling_bridge",
            "brother siblings two younger kids",
        ),
        (
            build_query_expansion_plan("What attributes describe John?"),
            "attribute_description_bridge",
            "volunteering food supplies toy drive",
        ),
    ]

    for plan, reason, expected_text in cases:
        assert expected_text in _expansion_query(plan, reason)


def test_query_expansion_covers_trait_and_adverse_trip_bridges() -> None:
    traits = build_query_expansion_plan(
        "What personality traits might Melanie say Caroline has?"
    )
    roadtrip = build_query_expansion_plan("Would Melanie go on another roadtrip soon?")

    assert "thoughtful authentic driven" in _expansion_query(
        traits,
        "personality_trait_bridge",
    )
    assert "thoughtful concern" in _expansion_query(
        traits,
        "personality_thoughtfulness_bridge",
    )
    assert "authentic real genuine" in _expansion_query(
        traits,
        "personality_authenticity_bridge",
    )
    assert "driven drive determined" in _expansion_query(
        traits,
        "personality_drive_bridge",
    )
    assert "accident scary scared bad start" in _expansion_query(
        roadtrip,
        "adverse_trip_bridge",
    )


def test_query_expansion_covers_generic_multimodal_evidence_bridges() -> None:
    screenshot = build_query_expansion_plan(
        "What text is written in this screenshot image?"
    )
    video = build_query_expansion_plan(
        "What did Alex say in the video about the launch?"
    )
    meeting = build_query_expansion_plan("What action items came from the meeting?")

    assert "ocr detected text written" in _expansion_query(
        screenshot,
        "visual_text_evidence_bridge",
    )
    assert screenshot.diagnostics()["query_expansion_reasons"].count(
        "visual_text_evidence_bridge"
    ) == 1
    assert "transcript speech said told" in _expansion_query(
        video,
        "video_transcript_evidence_bridge",
    )
    assert "transcript notes discussed decision" in _expansion_query(
        meeting,
        "meeting_evidence_bridge",
    )


def test_query_expansion_covers_source_evidence_bridge() -> None:
    source = build_query_expansion_plan("Show source citation for the Atlas decision")
    russian = build_query_expansion_plan("Покажи источник по решению Атлас")

    assert "source citation evidence quote" in _expansion_query(
        source,
        "source_evidence_bridge",
    )
    assert source.diagnostics()["query_expansion_reasons"].count(
        "source_evidence_bridge"
    ) == 1
    assert "источник ссылка доказательство" in _expansion_query(
        russian,
        "source_evidence_bridge",
    )


def test_query_expansion_covers_russian_multimodal_evidence_bridges() -> None:
    video = build_query_expansion_plan("Что Алекс сказал в видео про запуск?")
    screenshot = build_query_expansion_plan("Что написано на скриншоте?")

    assert "транскрипт сказал сказала" in _expansion_query(
        video,
        "video_transcript_evidence_bridge",
    )
    screenshot_expansion = _expansion_query(screenshot, "visual_text_evidence_bridge")
    assert "ocr" in screenshot_expansion
    assert "текст написано" in screenshot_expansion


def test_query_expansion_covers_generic_ally_inference_bridge() -> None:
    plan = build_query_expansion_plan("Would Melanie be considered an ally?")

    assert "supportive support acceptance" in _expansion_query(
        plan,
        "ally_support_bridge",
    )


def test_query_expansion_covers_temporal_change_bridges() -> None:
    latest = build_query_expansion_plan("What is the latest current Atlas decision?")
    changed = build_query_expansion_plan("What changed after the meeting with Alex?")
    before = build_query_expansion_plan("What was the plan before the call?")

    assert "latest current active newest" in _expansion_query(
        latest,
        "current_state_temporal_bridge",
    )
    assert latest.diagnostics()["query_expansion_reasons"].count(
        "current_state_temporal_bridge"
    ) == 1
    assert "changed change updated now" in _expansion_query(
        changed,
        "change_over_time_bridge",
    )
    assert "after later following" in _expansion_query(
        changed,
        "after_event_temporal_bridge",
    )
    assert "before earlier prior" in _expansion_query(
        before,
        "before_event_temporal_bridge",
    )


def test_query_expansion_covers_russian_temporal_change_bridges() -> None:
    current = build_query_expansion_plan("Какое актуальное решение по проекту Атлас?")
    changed = build_query_expansion_plan("Что изменилось после встречи с Алексом?")
    stale = build_query_expansion_plan("Устаревшее не учитывать, что сейчас актуально?")

    assert "актуальный текущий последний" in _expansion_query(
        current,
        "current_state_temporal_bridge",
    )
    assert "изменилось изменили стало" in _expansion_query(
        changed,
        "change_over_time_bridge",
    )
    assert "после позже затем" in _expansion_query(
        changed,
        "after_event_temporal_bridge",
    )
    assert "устаревший старый" in _expansion_query(
        stale,
        "stale_state_temporal_bridge",
    )


def test_best_query_relevance_uses_expansion_for_low_overlap_evidence() -> None:
    plan = build_query_expansion_plan("Where did Caroline move from 4 years ago?")

    query, reason, relevance = best_query_relevance(
        plan,
        text=(
            "D4:3 Caroline: This necklace was a gift from my grandma in my home "
            "country, Sweden, and reminds me of my roots."
        ),
    )

    assert query.startswith("Caroline ")
    assert reason == "relocation_origin_bridge"
    assert relevance.distinctive_term_hits >= 2


def test_best_query_relevance_uses_source_evidence_bridge() -> None:
    plan = build_query_expansion_plan("Show proof for the Atlas decision")

    _, reason, relevance = best_query_relevance(
        plan,
        text=(
            "Evidence quote from the meeting transcript: Alex approved the Atlas "
            "launch path."
        ),
    )

    assert reason == "source_evidence_bridge"
    assert relevance.distinctive_term_hits >= 2


def test_best_query_relevance_uses_specific_support_origin_bridge() -> None:
    plan = build_query_expansion_plan(
        "Would Caroline still want to pursue counseling as a career if she hadn't "
        "received support growing up?"
    )

    _, reason, relevance = best_query_relevance(
        plan,
        text=(
            "D3:5 Caroline: I've been blessed with loads of love and support "
            "throughout this journey, and I want to pass it on to others. "
            "By sharing our stories, we can build a strong, supportive community "
            "of hope."
        ),
    )

    assert reason == "support_origin_bridge"
    assert relevance.distinctive_term_hits >= 6


def test_best_query_relevance_uses_support_career_motivation_bridge() -> None:
    plan = build_query_expansion_plan(
        "Would Caroline still want to pursue counseling as a career if she hadn't "
        "received support growing up?"
    )

    _, reason, relevance = best_query_relevance(
        plan,
        text=(
            "D4:15 Caroline: My own journey and the support I got made a huge "
            "difference. I saw how counseling and support groups improved my life, "
            "so I started caring more about mental health. Now I'm passionate "
            "about creating a safe, inviting place for people to grow."
        ),
    )
    focused = score_query_relevance(
        query=_expansion_query(plan, "support_career_motivation_bridge"),
        text=(
            "D4:15 Caroline: My own journey and the support I got made a huge "
            "difference. I saw how counseling and support groups improved my life, "
            "so I started caring more about mental health. Now I'm passionate "
            "about creating a safe, inviting place for people to grow."
        ),
    )
    looser = score_query_relevance(
        query=_expansion_query(plan, "support_career_motivation_bridge"),
        text=(
            "D7:7 Caroline: I struggled with mental health, and support I got was "
            "really helpful. It made me realize how important it is for others to "
            "have a support system, so I started looking into counseling jobs."
        ),
    )

    assert reason == "support_career_motivation_bridge"
    assert relevance.distinctive_term_hits >= 10
    assert keyword_chunk_score(
        focused,
        query_expansion_reason="support_career_motivation_bridge",
    ) > keyword_chunk_score(
        looser,
        query_expansion_reason="support_career_motivation_bridge",
    )


def test_best_query_relevance_uses_education_career_field_bridge() -> None:
    plan = build_query_expansion_plan(
        "What fields would Caroline be likely to pursue in her educaton?"
    )

    _, options_reason, options_relevance = best_query_relevance(
        plan,
        text=(
            "D1:9 Caroline: Gonna continue my edu and check out career options, "
            "which is pretty exciting!"
        ),
    )
    _, counseling_reason, counseling_relevance = best_query_relevance(
        plan,
        text=(
            "D1:11 Caroline: I'm keen on counseling or working in mental health - "
            "I'd love to support those with similar issues."
        ),
    )

    assert options_reason == "education_career_field_bridge"
    assert options_relevance.distinctive_term_hits >= 5
    assert counseling_reason == "education_career_field_bridge"
    assert counseling_relevance.distinctive_term_hits >= 5


def test_best_query_relevance_uses_identity_and_relationship_status_bridges() -> None:
    identity = build_query_expansion_plan("What is Caroline's identity?")
    relationship = build_query_expansion_plan("What is Caroline's relationship status?")

    _, identity_reason, identity_relevance = best_query_relevance(
        identity,
        text=(
            "D1:5 Caroline: The transgender stories were so inspiring! "
            "visual query: transgender pride flag mural"
        ),
    )
    _, relationship_reason, relationship_relevance = best_query_relevance(
        relationship,
        text=(
            "D2:14 Caroline: It'll be tough as a single parent, but I'm up for "
            "the challenge after that tough breakup."
        ),
    )
    _, breakup_reason, breakup_relevance = best_query_relevance(
        relationship,
        text=(
            "D3:13 Caroline: My friends, family and mentors are my rocks and "
            "support system, especially after that tough breakup."
        ),
    )

    assert identity_reason == "identity_bridge"
    assert identity_relevance.distinctive_term_hits >= 5
    assert relationship_reason == "relationship_status_bridge"
    assert relationship_relevance.distinctive_term_hits >= 5
    assert breakup_reason == "relationship_status_bridge"
    assert breakup_relevance.distinctive_term_hits >= 5


def test_best_query_relevance_uses_trait_and_adverse_trip_bridges() -> None:
    traits = build_query_expansion_plan(
        "What personality traits might Melanie say Caroline has?"
    )
    roadtrip = build_query_expansion_plan("Would Melanie go on another roadtrip soon?")

    _, trait_reason, trait_relevance = best_query_relevance(
        traits,
        text=(
            "D16:18 Melanie: Thank you for your concern, you're so thoughtful. "
            "D13:16 Melanie: You really care about being real and helping others. "
            "D7:4 Melanie: Your drive to help is awesome."
        ),
    )
    _, trip_reason, trip_relevance = best_query_relevance(
        roadtrip,
        text=(
            "D18:1 Melanie: That roadtrip was insane and we were all freaked "
            "when my son got into an accident. D18:3 Melanie: Our trip got off "
            "to a bad start. I was really scared."
        ),
    )

    assert trait_reason == "personality_trait_bridge"
    assert trait_relevance.distinctive_term_hits >= 5
    assert trip_reason == "adverse_trip_bridge"
    assert trip_relevance.distinctive_term_hits >= 5


def test_trait_query_decomposition_targets_single_trait_turns() -> None:
    plan = build_query_expansion_plan(
        "What personality traits might Melanie say Caroline has?"
    )

    _, thoughtful_reason, thoughtful = best_query_relevance(
        plan,
        text=(
            "D16:18 Melanie: The sign was just a precaution, but thank you for "
            "your concern, you're so thoughtful!"
        ),
    )
    _, authentic_reason, authentic = best_query_relevance(
        plan,
        text=(
            "D13:16 Melanie: You really care about being real and helping others."
        ),
    )
    _, drive_reason, drive = best_query_relevance(
        plan,
        text=(
            "D7:4 Melanie: Your drive to help is awesome! What's your plan to "
            "pitch in?"
        ),
    )

    assert thoughtful_reason == "personality_thoughtfulness_bridge"
    assert thoughtful.distinctive_term_hits >= 4
    assert authentic_reason == "personality_authenticity_bridge"
    assert authentic.distinctive_term_hits >= 4
    assert drive_reason == "personality_drive_bridge"
    assert drive.distinctive_term_hits >= 5


def test_best_query_relevance_uses_specific_outdoor_nature_memory_bridge() -> None:
    plan = build_query_expansion_plan(
        "Would Melanie be more interested in going to a national park or a theme park?"
    )

    _, reason, relevance = best_query_relevance(
        plan,
        text=(
            "D10:14 Melanie: I'll always remember our camping trip last year "
            "when we saw the Perseid meteor shower. It was amazing watching "
            "the sky light up and feeling at one with the universe."
        ),
    )

    assert reason == "outdoor_nature_memory_bridge"
    assert relevance.distinctive_term_hits >= 6


def test_best_query_relevance_bridges_classical_music_preferences() -> None:
    plan = build_query_expansion_plan(
        'Would Melanie likely enjoy the song "The Four Seasons" by Vivaldi?'
    )

    _, reason, relevance = best_query_relevance(
        plan,
        text=(
            "D15:28 Melanie: I'm a fan of both classical like Bach and Mozart, "
            "as well as modern music like Ed Sheeran's Perfect."
        ),
    )

    assert reason == "classical_music_preference_bridge"
    assert relevance.distinctive_term_hits >= 4


def test_keyword_chunk_score_separates_stronger_evidence_from_loose_match() -> None:
    query = (
        "Melanie camping trip campfire meteor shower nature outdoors"
    )
    strong = score_query_relevance(
        query=query,
        text=(
            "D10:12 D10:14 Melanie: Melanie's family tradition includes a "
            "camping trip where they roast marshmallows and tell stories around "
            "the campfire. Melanie and her family watched the Perseid meteor "
            "shower during a camping trip last year."
        ),
    )
    loose = score_query_relevance(
        query=query,
        text="D15:2 Melanie took her kids to a park and enjoyed seeing them outdoors.",
    )

    assert keyword_chunk_score(
        strong,
        query_expansion_reason="outdoor_preference_bridge",
    ) > keyword_chunk_score(
        loose,
        query_expansion_reason="outdoor_preference_bridge",
    )


def _expansion_query(plan: QueryExpansionPlan, reason: str) -> str:
    for expansion in plan.expansions:
        if expansion.reason == reason:
            return expansion.query
    raise AssertionError(f"missing expansion reason: {reason}")
