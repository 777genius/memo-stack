from infinity_context_core.application.context_action_roles import action_role_rerank_signal


def test_action_role_supports_lowercase_direct_person_recipient() -> None:
    matched = action_role_rerank_signal(
        query="what did alex promise maria after the atlas call?",
        text="D3:4 Alex promised Maria he would send the Atlas invoice after the call.",
    )
    reversed_roles = action_role_rerank_signal(
        query="what did alex promise maria after the atlas call?",
        text="D3:4 Maria promised Alex she would send the Atlas invoice after the call.",
    )

    assert matched.boost > 0
    assert matched.reason == "action_role_actor_recipient_match"
    assert reversed_roles.penalty > 0
    assert reversed_roles.reason == "action_role_actor_recipient_reversed"


def test_action_role_does_not_treat_lowercase_direct_object_as_recipient() -> None:
    signal = action_role_rerank_signal(
        query="what did alex send invoice after the atlas call?",
        text="D3:4 Alex sent the invoice after the Atlas call.",
    )

    assert signal.boost > 0
    assert signal.reason == "action_role_actor_match"


def test_action_role_does_not_treat_reported_subject_as_query_actor() -> None:
    signal = action_role_rerank_signal(
        query="What did Alex promise Maria after the Atlas call?",
        text="D3:4 Alex heard Dana promised Maria she would send the invoice.",
    )

    assert signal.penalty > 0
    assert signal.reason == "action_role_actor_mismatch"


def test_action_role_does_not_treat_reported_subject_as_recipient_actor() -> None:
    signal = action_role_rerank_signal(
        query="Who recommended Becoming Nicole to Melanie?",
        text="D3:4 Melanie heard Caroline recommended Becoming Nicole to Dana.",
    )

    assert signal.boost == 0.0
    assert signal.penalty == 0.0
    assert signal.reason == ""


def test_action_role_boosts_generic_owner_responsibility_evidence() -> None:
    signal = action_role_rerank_signal(
        query="Who is responsible for the Atlas invoice?",
        text="D3:4 Alex is responsible for the Atlas invoice follow-up.",
    )

    assert signal.boost > 0
    assert signal.reason == "action_role_owner_evidence"


def test_action_role_matches_named_owner_responsibility() -> None:
    matched = action_role_rerank_signal(
        query="Is Alex responsible for the Atlas invoice?",
        text="D3:4 Alex is responsible for the Atlas invoice follow-up.",
    )
    mismatch = action_role_rerank_signal(
        query="Is Alex responsible for the Atlas invoice?",
        text="D3:4 Maria is responsible for the Atlas invoice follow-up.",
    )

    assert matched.boost > 0
    assert matched.reason == "action_role_owner_match"
    assert mismatch.penalty > 0
    assert mismatch.reason == "action_role_owner_mismatch"


def test_action_role_extracts_recommender_from_suggestion_source_query() -> None:
    matched = action_role_rerank_signal(
        query="What book did Melanie read from Caroline's suggestion?",
        text="Caroline recommended Becoming Nicole by Amy Ellis Nutt to Melanie.",
    )
    reversed_roles = action_role_rerank_signal(
        query="What book did Melanie read from Caroline's suggestion?",
        text="Melanie recommended Becoming Nicole to Caroline.",
    )

    assert matched.boost > 0
    assert matched.reason == "action_role_actor_recipient_match"
    assert reversed_roles.penalty > 0
    assert reversed_roles.reason == "action_role_actor_recipient_reversed"


def test_action_role_extracts_recommender_from_after_recommended_query() -> None:
    matched = action_role_rerank_signal(
        query="What book did Melanie read after Caroline recommended it?",
        text="Caroline recommended Becoming Nicole by Amy Ellis Nutt to Melanie.",
    )
    reversed_roles = action_role_rerank_signal(
        query="What book did Melanie read after Caroline recommended it?",
        text="Melanie recommended Becoming Nicole to Caroline.",
    )

    assert matched.boost > 0
    assert matched.reason == "action_role_actor_recipient_match"
    assert reversed_roles.penalty > 0
    assert reversed_roles.reason == "action_role_actor_recipient_reversed"


def test_action_role_treats_suggested_as_recommendation_evidence() -> None:
    signal = action_role_rerank_signal(
        query="Who suggested Becoming Nicole to Melanie?",
        text="Caroline suggested Becoming Nicole by Amy Ellis Nutt to Melanie.",
    )

    assert signal.boost > 0
    assert signal.reason == "action_role_recipient_match"


def test_action_role_extracts_requested_recipient_from_actor_question() -> None:
    explicit_recipient = action_role_rerank_signal(
        query="Who did Caroline recommend Becoming Nicole to?",
        text="Caroline recommended Becoming Nicole by Amy Ellis Nutt to Melanie.",
    )
    actor_only = action_role_rerank_signal(
        query="Who did Caroline recommend Becoming Nicole to?",
        text="Caroline recommended Becoming Nicole by Amy Ellis Nutt.",
    )
    wrong_actor = action_role_rerank_signal(
        query="Who did Caroline recommend Becoming Nicole to?",
        text="Melanie recommended Becoming Nicole to Caroline.",
    )

    assert explicit_recipient.boost > 0
    assert explicit_recipient.reason == "action_role_actor_to_recipient_evidence"
    assert actor_only.penalty > 0
    assert actor_only.reason == "action_role_requested_recipient_missing"
    assert wrong_actor.penalty > 0
    assert wrong_actor.reason == "action_role_actor_mismatch"


def test_action_role_extracts_requested_recipient_with_trailing_context() -> None:
    signal = action_role_rerank_signal(
        query="Who did Caroline recommend Becoming Nicole to during the book club?",
        text="Caroline recommended Becoming Nicole by Amy Ellis Nutt to Melanie.",
    )

    assert signal.boost > 0
    assert signal.reason == "action_role_actor_to_recipient_evidence"


def test_action_role_extracts_requested_recipient_from_to_whom_question() -> None:
    signal = action_role_rerank_signal(
        query="To whom did Caroline suggest Becoming Nicole?",
        text="Caroline suggested Becoming Nicole by Amy Ellis Nutt to Melanie.",
    )

    assert signal.boost > 0
    assert signal.reason == "action_role_actor_to_recipient_evidence"


def test_action_role_supports_russian_recommendation_direct_recipient() -> None:
    matched = action_role_rerank_signal(
        query="Кто посоветовал Мелани прочитать Becoming Nicole?",
        text="Кэролайн посоветовала Мелани прочитать Becoming Nicole.",
    )
    mismatch = action_role_rerank_signal(
        query="Кто посоветовал Мелани прочитать Becoming Nicole?",
        text="Мелани посоветовала Кэролайн прочитать Becoming Nicole.",
    )

    assert matched.boost > 0
    assert matched.reason == "action_role_recipient_match"
    assert mismatch.penalty > 0
    assert mismatch.reason == "action_role_recipient_mismatch"


def test_action_role_extracts_requested_recipient_from_russian_question() -> None:
    matched = action_role_rerank_signal(
        query="Кому Кэролайн посоветовала прочитать Becoming Nicole?",
        text="Кэролайн посоветовала Мелани прочитать Becoming Nicole.",
    )
    mismatch = action_role_rerank_signal(
        query="Кому Кэролайн посоветовала прочитать Becoming Nicole?",
        text="Мелани посоветовала Кэролайн прочитать Becoming Nicole.",
    )

    assert matched.boost > 0
    assert matched.reason == "action_role_actor_to_recipient_evidence"
    assert mismatch.penalty > 0
    assert mismatch.reason == "action_role_actor_mismatch"


def test_action_role_extracts_recipient_from_whose_suggestion_query() -> None:
    matched = action_role_rerank_signal(
        query="Whose suggestion did Melanie follow when she read Becoming Nicole?",
        text="Caroline recommended Becoming Nicole by Amy Ellis Nutt to Melanie.",
    )
    reversed_roles = action_role_rerank_signal(
        query="Whose suggestion did Melanie follow when she read Becoming Nicole?",
        text="Melanie recommended Becoming Nicole to Caroline.",
    )

    assert matched.boost > 0
    assert matched.reason == "action_role_recipient_match"
    assert reversed_roles.penalty > 0
    assert reversed_roles.reason == "action_role_recipient_mismatch"


def test_action_role_extracts_recipient_from_gave_suggestion_query() -> None:
    direct_recipient = action_role_rerank_signal(
        query="Who gave Melanie the suggestion to read Becoming Nicole?",
        text="Caroline recommended Becoming Nicole by Amy Ellis Nutt to Melanie.",
    )
    preposition_recipient = action_role_rerank_signal(
        query="Who offered the recommendation to Melanie?",
        text="Caroline suggested Becoming Nicole by Amy Ellis Nutt to Melanie.",
    )
    mismatch = action_role_rerank_signal(
        query="Who gave Melanie the suggestion to read Becoming Nicole?",
        text="Caroline suggested Becoming Nicole by Amy Ellis Nutt to Dana.",
    )

    assert direct_recipient.boost > 0
    assert direct_recipient.reason == "action_role_recipient_match"
    assert preposition_recipient.boost > 0
    assert preposition_recipient.reason == "action_role_recipient_match"
    assert mismatch.boost == 0.0
    assert mismatch.penalty == 0.0


def test_action_role_extracts_actor_from_nominal_decision_query() -> None:
    matched = action_role_rerank_signal(
        query="What decision did Caroline make after the interview?",
        text="D19:3 Caroline made the decision to continue adoption after the agency interview.",
    )
    mismatch = action_role_rerank_signal(
        query="What decision did Caroline make after the interview?",
        text="D19:3 Dana made the decision to continue adoption after the agency interview.",
    )

    assert matched.boost > 0
    assert matched.reason == "action_role_actor_match"
    assert mismatch.penalty > 0
    assert mismatch.reason == "action_role_actor_mismatch"


def test_action_role_extracts_recipient_from_nominal_promise_query() -> None:
    matched = action_role_rerank_signal(
        query="What promise did Alex make to Maria after the Atlas call?",
        text="D3:4 Alex made a promise to Maria to send the Atlas invoice after the call.",
    )
    reversed_roles = action_role_rerank_signal(
        query="What promise did Alex make to Maria after the Atlas call?",
        text="D3:4 Maria made a promise to Alex to send the Atlas invoice after the call.",
    )

    assert matched.boost > 0
    assert matched.reason == "action_role_actor_recipient_match"
    assert reversed_roles.penalty > 0
    assert reversed_roles.reason == "action_role_actor_recipient_reversed"
