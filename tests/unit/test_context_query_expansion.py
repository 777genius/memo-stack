from infinity_context_core.application.context_query_expansion import (
    QueryExpansionPlan,
    build_query_expansion_plan,
)
from infinity_context_core.application.context_relevance import score_query_relevance
from infinity_context_core.application.use_cases.build_context import (
    _best_query_relevance,
    _keyword_chunk_score,
)


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


def test_best_query_relevance_uses_expansion_for_low_overlap_evidence() -> None:
    plan = build_query_expansion_plan("Where did Caroline move from 4 years ago?")

    query, reason, relevance = _best_query_relevance(
        plan,
        text=(
            "D4:3 Caroline: This necklace was a gift from my grandma in my home "
            "country, Sweden, and reminds me of my roots."
        ),
    )

    assert query.startswith("Caroline ")
    assert reason == "relocation_origin_bridge"
    assert relevance.distinctive_term_hits >= 2


def test_best_query_relevance_uses_specific_support_origin_bridge() -> None:
    plan = build_query_expansion_plan(
        "Would Caroline still want to pursue counseling as a career if she hadn't "
        "received support growing up?"
    )

    _, reason, relevance = _best_query_relevance(
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


def test_best_query_relevance_uses_specific_outdoor_nature_memory_bridge() -> None:
    plan = build_query_expansion_plan(
        "Would Melanie be more interested in going to a national park or a theme park?"
    )

    _, reason, relevance = _best_query_relevance(
        plan,
        text=(
            "D10:14 Melanie: I'll always remember our camping trip last year "
            "when we saw the Perseid meteor shower. It was amazing watching "
            "the sky light up and feeling at one with the universe."
        ),
    )

    assert reason == "outdoor_nature_memory_bridge"
    assert relevance.distinctive_term_hits >= 6


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

    assert _keyword_chunk_score(
        strong,
        query_expansion_reason="outdoor_preference_bridge",
    ) > _keyword_chunk_score(
        loose,
        query_expansion_reason="outdoor_preference_bridge",
    )


def _expansion_query(plan: QueryExpansionPlan, reason: str) -> str:
    for expansion in plan.expansions:
        if expansion.reason == reason:
            return expansion.query
    raise AssertionError(f"missing expansion reason: {reason}")
