"""Role-sensitive action matching for deterministic memory reranking."""

from __future__ import annotations

import re
from dataclasses import dataclass

_LABEL_RE = r"[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё._-]{1,39}"
_QUERY_LABEL_RE = r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё._-]{1,39}"
_ACTION_VERB_RE = (
    r"recommend(?:ed|s|ing)?|suggest(?:ed|s|ing)?|"
    r"promise(?:d|s|ing)?|decid(?:e|ed|es|ing)|"
    r"ask(?:ed|s|ing)?|assign(?:ed|s|ing)?|approv(?:e|ed|es|ing)|"
    r"send|sent|give|gave|tell|told|"
    r"рекомендовал(?:а)?|порекомендовал(?:а)?|посоветовал(?:а)?|"
    r"пообещал(?:а)?|обещал(?:а)?|решил(?:а)?|"
    r"спросил(?:а)?|назначил(?:а)?|одобрил(?:а)?|сказал(?:а)?"
)
_QUESTION_ACTION_RE = re.compile(
    rf"\b(?:what\s+did\s+|did\s+|what\s+has\s+|has\s+)?"
    rf"(?P<actor>{_QUERY_LABEL_RE})\s+"
    rf"(?P<verb>{_ACTION_VERB_RE})\b",
    re.IGNORECASE,
)
_WHO_TO_ACTION_RE = re.compile(
    rf"\bwho\s+(?P<verb>{_ACTION_VERB_RE})\b"
    rf"(?P<object>.{{0,120}}?)\b(?:to|for)\s+(?P<recipient>{_QUERY_LABEL_RE})\b",
    re.IGNORECASE,
)
_WHO_DID_ACTOR_ACTION_TO_QUERY_RE = re.compile(
    rf"\b(?:who|whom)\s+did\s+(?P<actor>{_QUERY_LABEL_RE})\s+"
    rf"(?P<verb>{_ACTION_VERB_RE})\b"
    rf"(?P<object>.{{0,120}}?)\b(?:to|for)\b"
    rf"(?=\s*(?:\?|$|in\b|during\b|after\b|before\b|on\b|at\b))",
    re.IGNORECASE | re.DOTALL,
)
_TO_WHOM_DID_ACTOR_ACTION_QUERY_RE = re.compile(
    rf"\b(?:to|for)\s+whom\s+did\s+(?P<actor>{_QUERY_LABEL_RE})\s+"
    rf"(?P<verb>{_ACTION_VERB_RE})\b",
    re.IGNORECASE | re.DOTALL,
)
_NOMINAL_ACTION_QUERY_RE = re.compile(
    r"\b(?:what|which)\s+"
    r"(?P<noun>decision|promise|recommendation|suggestion)\s+"
    rf"did\s+(?P<actor>{_QUERY_LABEL_RE})\s+(?:make|give|offer)\b"
    r"(?P<tail>.{0,120})",
    re.IGNORECASE | re.DOTALL,
)
_OWNER_RESPONSIBILITY_QUERY_RE = re.compile(
    rf"\b(?:(?:who\s+(?:is|was|'s)\s+(?:responsible|(?:the\s+)?owner)|who\s+owns)"
    rf"|(?:is|was)\s+(?P<owner_after>{_QUERY_LABEL_RE})\s+responsible"
    rf"|(?P<owner_before>{_QUERY_LABEL_RE})\s+"
    rf"(?:is|was|'s)\s+(?:responsible|(?:the\s+)?owner)"
    rf"|(?P<owner_owns>{_QUERY_LABEL_RE})\s+owns?)\b",
    re.IGNORECASE,
)
_SUGGESTION_SOURCE_QUERY_RE = re.compile(
    rf"\b(?P<recipient>{_QUERY_LABEL_RE})\s+"
    r"(?:read|watched|tried|bought|used|visited|listened|started|played|made|ate)\b"
    r".{0,120}\b(?:from|based\s+on|because\s+of|after)\s+"
    rf"(?P<actor>{_QUERY_LABEL_RE})(?:'s|s')?\s+"
    r"(?:suggestion|recommendation|advice)\b",
    re.IGNORECASE | re.DOTALL,
)
_RECIPIENT_AFTER_ACTOR_RECOMMENDATION_QUERY_RE = re.compile(
    rf"\b(?P<recipient>{_QUERY_LABEL_RE})\s+"
    r"(?:read|watched|tried|bought|used|visited|listened|started|played|made|ate)\b"
    r".{0,120}\b(?:after|because|since|when)\s+"
    rf"(?P<actor>{_QUERY_LABEL_RE})\s+"
    r"(?P<verb>recommend(?:ed|s|ing)?|suggest(?:ed|s|ing)?)\b",
    re.IGNORECASE | re.DOTALL,
)
_WHOSE_SUGGESTION_QUERY_RE = re.compile(
    r"\bwhose\s+(?:suggestion|recommendation|advice)\s+did\s+"
    rf"(?P<recipient>{_QUERY_LABEL_RE})\s+"
    r"(?:follow|take|use|read|watch|try|buy|visit|listen|start|play|make|eat)\b",
    re.IGNORECASE,
)
_WHO_GAVE_SUGGESTION_TO_QUERY_RE = re.compile(
    r"\bwho\s+(?:gave|offered|made)\b"
    r".{0,80}\b(?:suggestion|recommendation|advice)\b"
    rf".{{0,80}}\b(?:to|for)\s+(?P<recipient>{_QUERY_LABEL_RE})\b",
    re.IGNORECASE | re.DOTALL,
)
_WHO_GAVE_DIRECT_SUGGESTION_QUERY_RE = re.compile(
    r"\bwho\s+(?:gave|offered|made)\s+"
    rf"(?P<recipient>{_QUERY_LABEL_RE})\b"
    r".{0,80}\b(?:suggestion|recommendation|advice)\b",
    re.IGNORECASE | re.DOTALL,
)
_RU_WHO_DIRECT_RECOMMENDATION_QUERY_RE = re.compile(
    r"\bкто\s+"
    r"(?P<verb>рекомендовал(?:а)?|порекомендовал(?:а)?|посоветовал(?:а)?)\s+"
    rf"(?P<recipient>{_QUERY_LABEL_RE})\b",
    re.IGNORECASE | re.DOTALL,
)
_RU_TO_WHOM_ACTOR_ACTION_QUERY_RE = re.compile(
    rf"\bкому\s+(?P<actor>{_QUERY_LABEL_RE})\s+"
    rf"(?P<verb>{_ACTION_VERB_RE})\b",
    re.IGNORECASE | re.DOTALL,
)
_REPORTED_SUBJECT_SHIFT_RE = re.compile(
    rf"\b(?:heard|learned|mentioned|reported|said|told|wrote)\b"
    rf".{{0,80}}\b{_LABEL_RE}\W*$",
    re.IGNORECASE | re.DOTALL,
)
_QUERY_LABEL_STOP_WORDS = frozenset(
    {
        "did",
        "has",
        "what",
        "who",
        "whom",
        "whose",
        "anybody",
        "anyone",
        "buy",
        "people",
        "person",
        "eat",
        "follow",
        "listen",
        "make",
        "play",
        "read",
        "somebody",
        "someone",
        "start",
        "take",
        "try",
        "use",
        "visit",
        "watch",
        "что",
        "кто",
        "кого",
        "кому",
    }
)
_TEXT_LABEL_STOP_WORDS = _QUERY_LABEL_STOP_WORDS.union(
    {
        "project",
        "transcript",
    }
)
_ACTION_ROLE_MATCH_BOOST = 0.024
_ACTION_ROLE_REQUESTED_RECIPIENT_EVIDENCE_BOOST = 0.021
_ACTION_ROLE_ACTOR_MATCH_BOOST = 0.018
_ACTION_ROLE_RECIPIENT_MATCH_BOOST = 0.016
_ACTION_ROLE_OWNER_EVIDENCE_BOOST = 0.014
_ACTION_ROLE_MISMATCH_PENALTY = 0.034
_ACTION_ROLE_RECIPIENT_MISMATCH_PENALTY = 0.028
_ACTION_ROLE_REQUESTED_RECIPIENT_MISSING_PENALTY = 0.014
_DIRECT_RECIPIENT_VERBS = frozenset({"ask", "assign", "give", "promise", "tell"})
_DIRECT_RECIPIENT_OBJECT_STOP_WORDS = frozenset(
    {
        "decision",
        "doc",
        "document",
        "email",
        "file",
        "image",
        "invoice",
        "link",
        "message",
        "note",
        "notes",
        "photo",
        "plan",
        "report",
        "screenshot",
        "story",
        "task",
        "update",
    }
)


@dataclass(frozen=True)
class ActionRoleRerankSignal:
    boost: float = 0.0
    penalty: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class _ActionRoleQuery:
    verb_key: str
    actor_label: str = ""
    recipient_label: str = ""
    owner_label: str = ""
    owner_requested: bool = False
    recipient_requested: bool = False


def action_role_rerank_signal(*, query: str, text: str) -> ActionRoleRerankSignal:
    """Return bounded role-order signal for action questions.

    This intentionally treats provider/output text as evidence only: it adjusts ranking,
    but never rewrites or asserts canonical facts.
    """

    role_query = _action_role_query(query)
    if role_query is None:
        return ActionRoleRerankSignal()
    if role_query.owner_requested:
        return _owner_responsibility_signal(role_query, text)
    if role_query.actor_label:
        return _actor_action_signal(role_query, text)
    if role_query.recipient_label:
        return _recipient_action_signal(role_query, text)
    return ActionRoleRerankSignal()


def _action_role_query(query: str) -> _ActionRoleQuery | None:
    owner_match = _OWNER_RESPONSIBILITY_QUERY_RE.search(query)
    if owner_match is not None:
        owner = _clean_label(
            owner_match.group("owner_after")
            or owner_match.group("owner_before")
            or owner_match.group("owner_owns")
            or ""
        )
        return _ActionRoleQuery(
            verb_key="owner",
            owner_label=owner,
            owner_requested=True,
        )

    match = _WHO_TO_ACTION_RE.search(query)
    if match is not None:
        verb_key = _canonical_verb_key(match.group("verb"))
        recipient = _clean_label(match.group("recipient"))
        if verb_key and recipient:
            return _ActionRoleQuery(verb_key=verb_key, recipient_label=recipient)

    match = _WHOSE_SUGGESTION_QUERY_RE.search(query)
    if match is not None:
        recipient = _clean_label(match.group("recipient"))
        if recipient:
            return _ActionRoleQuery(
                verb_key="recommend",
                recipient_label=recipient,
            )

    for pattern in (
        _WHO_GAVE_SUGGESTION_TO_QUERY_RE,
        _WHO_GAVE_DIRECT_SUGGESTION_QUERY_RE,
    ):
        match = pattern.search(query)
        if match is not None:
            recipient = _clean_label(match.group("recipient"))
            if recipient:
                return _ActionRoleQuery(
                    verb_key="recommend",
                    recipient_label=recipient,
                )

    match = _RU_WHO_DIRECT_RECOMMENDATION_QUERY_RE.search(query)
    if match is not None:
        recipient = _clean_label(match.group("recipient"))
        if recipient:
            return _ActionRoleQuery(
                verb_key="recommend",
                recipient_label=recipient,
            )

    for pattern in (
        _SUGGESTION_SOURCE_QUERY_RE,
        _RECIPIENT_AFTER_ACTOR_RECOMMENDATION_QUERY_RE,
    ):
        match = pattern.search(query)
        if match is not None:
            actor = _clean_label(match.group("actor"))
            recipient = _clean_label(match.group("recipient"))
            if actor and recipient:
                return _ActionRoleQuery(
                    verb_key="recommend",
                    actor_label=actor,
                    recipient_label=recipient,
                )

    for pattern in (
        _WHO_DID_ACTOR_ACTION_TO_QUERY_RE,
        _TO_WHOM_DID_ACTOR_ACTION_QUERY_RE,
        _RU_TO_WHOM_ACTOR_ACTION_QUERY_RE,
    ):
        match = pattern.search(query)
        if match is not None:
            actor = _clean_label(match.group("actor"))
            verb_key = _canonical_verb_key(match.group("verb"))
            if actor and verb_key:
                return _ActionRoleQuery(
                    verb_key=verb_key,
                    actor_label=actor,
                    recipient_requested=True,
                )

    match = _NOMINAL_ACTION_QUERY_RE.search(query)
    if match is not None:
        actor = _clean_label(match.group("actor"))
        verb_key = _canonical_nominal_action(match.group("noun"))
        recipient = _recipient_in_tail(match.group("tail") or "")
        if actor and verb_key:
            return _ActionRoleQuery(
                verb_key=verb_key,
                actor_label=actor,
                recipient_label=recipient,
            )

    match = _QUESTION_ACTION_RE.search(query)
    if match is None:
        return None
    actor = _clean_label(match.group("actor"))
    verb_key = _canonical_verb_key(match.group("verb"))
    if not actor or not verb_key:
        return None
    recipient = _recipient_after_action(
        query,
        match_end=match.end(),
        verb_key=verb_key,
    )
    return _ActionRoleQuery(
        verb_key=verb_key,
        actor_label=actor,
        recipient_label=recipient,
    )


def _actor_action_signal(
    role_query: _ActionRoleQuery,
    text: str,
) -> ActionRoleRerankSignal:
    actor = role_query.actor_label
    recipient = role_query.recipient_label
    verb_key = role_query.verb_key
    if recipient and _has_ordered_action(text, actor=actor, verb_key=verb_key, target=recipient):
        return ActionRoleRerankSignal(
            boost=_ACTION_ROLE_MATCH_BOOST,
            reason="action_role_actor_recipient_match",
        )
    if recipient and _has_ordered_action(text, actor=recipient, verb_key=verb_key, target=actor):
        return ActionRoleRerankSignal(
            penalty=_ACTION_ROLE_MISMATCH_PENALTY,
            reason="action_role_actor_recipient_reversed",
        )
    if role_query.recipient_requested and _has_actor_action_to_any_recipient(
        text,
        actor=actor,
        verb_key=verb_key,
    ):
        return ActionRoleRerankSignal(
            boost=_ACTION_ROLE_REQUESTED_RECIPIENT_EVIDENCE_BOOST,
            reason="action_role_actor_to_recipient_evidence",
        )
    if _has_actor_action(text, actor=actor, verb_key=verb_key):
        if role_query.recipient_requested:
            return ActionRoleRerankSignal(
                penalty=_ACTION_ROLE_REQUESTED_RECIPIENT_MISSING_PENALTY,
                reason="action_role_requested_recipient_missing",
            )
        return ActionRoleRerankSignal(
            boost=_ACTION_ROLE_ACTOR_MATCH_BOOST,
            reason="action_role_actor_match",
        )
    if _has_non_actor_action(text, expected_actor=actor, verb_key=verb_key):
        return ActionRoleRerankSignal(
            penalty=_ACTION_ROLE_MISMATCH_PENALTY,
            reason="action_role_actor_mismatch",
        )
    return ActionRoleRerankSignal()


def _recipient_action_signal(
    role_query: _ActionRoleQuery,
    text: str,
) -> ActionRoleRerankSignal:
    recipient = role_query.recipient_label
    verb_key = role_query.verb_key
    if _has_action_to_recipient(text, recipient=recipient, verb_key=verb_key):
        return ActionRoleRerankSignal(
            boost=_ACTION_ROLE_RECIPIENT_MATCH_BOOST,
            reason="action_role_recipient_match",
        )
    if _recipient_acts_to_other(text, recipient=recipient, verb_key=verb_key):
        return ActionRoleRerankSignal(
            penalty=_ACTION_ROLE_RECIPIENT_MISMATCH_PENALTY,
            reason="action_role_recipient_mismatch",
        )
    return ActionRoleRerankSignal()


def _owner_responsibility_signal(
    role_query: _ActionRoleQuery,
    text: str,
) -> ActionRoleRerankSignal:
    owner = role_query.owner_label
    if not owner:
        if _owner_labels_in_text(text):
            return ActionRoleRerankSignal(
                boost=_ACTION_ROLE_OWNER_EVIDENCE_BOOST,
                reason="action_role_owner_evidence",
            )
        return ActionRoleRerankSignal()
    owner_key = _normalized_label(owner)
    owner_labels = {_normalized_label(label) for label in _owner_labels_in_text(text)}
    if owner_key in owner_labels:
        return ActionRoleRerankSignal(
            boost=_ACTION_ROLE_ACTOR_MATCH_BOOST,
            reason="action_role_owner_match",
        )
    if owner_labels:
        return ActionRoleRerankSignal(
            penalty=_ACTION_ROLE_MISMATCH_PENALTY,
            reason="action_role_owner_mismatch",
        )
    return ActionRoleRerankSignal()


def _owner_labels_in_text(text: str) -> frozenset[str]:
    labels: set[str] = set()
    for pattern in (
        rf"(?P<label>{_LABEL_RE})\b.{{0,80}}\b(?:owns?|owner|responsible)\b",
        rf"\b(?:owner|responsible)\b.{{0,80}}\b(?P<label>{_LABEL_RE})\b",
        rf"\bassigned\s+to\s+(?P<label>{_LABEL_RE})\b",
    ):
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            label = _clean_label(match.group("label"))
            if label:
                labels.add(label)
    return frozenset(labels)


def _has_ordered_action(
    text: str,
    *,
    actor: str,
    verb_key: str,
    target: str,
) -> bool:
    return bool(
        _ordered_action_match_iter(
            text,
            actor=actor,
            verb_key=verb_key,
            tail_pattern=rf".{{0,100}}{_label_pattern(target)}",
        )
    )


def _ordered_action_match_iter(
    text: str,
    *,
    actor: str,
    verb_key: str,
    tail_pattern: str,
) -> bool:
    pattern = re.compile(
        rf"{_label_pattern(actor)}(?P<gap>.{{0,80}}?)\b(?:{_verb_forms(verb_key)})\b"
        rf"{tail_pattern}",
        flags=re.IGNORECASE | re.DOTALL,
    )
    return any(
        not _reported_subject_shift_before_action(match.group("gap"))
        for match in pattern.finditer(text)
    )


def _has_actor_action(text: str, *, actor: str, verb_key: str) -> bool:
    return _ordered_action_match_iter(
        text,
        actor=actor,
        verb_key=verb_key,
        tail_pattern="",
    )


def _has_actor_action_to_any_recipient(text: str, *, actor: str, verb_key: str) -> bool:
    preposition_pattern = re.compile(
        rf"{_label_pattern(actor)}(?P<gap>.{{0,80}}?)\b(?:{_verb_forms(verb_key)})\b"
        rf".{{0,140}}\b(?:to|for)\s+(?P<recipient>{_LABEL_RE})\b",
        re.IGNORECASE | re.DOTALL,
    )
    for match in preposition_pattern.finditer(text):
        if _reported_subject_shift_before_action(match.group("gap")):
            continue
        if _clean_label(match.group("recipient")):
            return True
    if verb_key != "recommend":
        return False
    russian_direct_pattern = re.compile(
        rf"{_label_pattern(actor)}(?P<gap>.{{0,80}}?)"
        rf"\b(?:{_russian_recommendation_forms()})\b\s+"
        rf"(?P<recipient>{_LABEL_RE})\b",
        re.IGNORECASE | re.DOTALL,
    )
    for match in russian_direct_pattern.finditer(text):
        if _reported_subject_shift_before_action(match.group("gap")):
            continue
        if _clean_label(match.group("recipient")):
            return True
    return False


def _reported_subject_shift_before_action(gap: str) -> bool:
    return bool(_REPORTED_SUBJECT_SHIFT_RE.search(gap))


def _has_non_actor_action(text: str, *, expected_actor: str, verb_key: str) -> bool:
    pattern = re.compile(
        rf"(?=\b(?P<actor>{_LABEL_RE})\b(?P<gap>.{{0,80}}?)"
        rf"\b(?:{_verb_forms(verb_key)})\b)",
        re.IGNORECASE | re.DOTALL,
    )
    expected = _normalized_label(expected_actor)
    for match in pattern.finditer(text):
        if _reported_subject_shift_before_action(match.group("gap")):
            continue
        actor = _clean_label(match.group("actor"))
        if actor and _normalized_label(actor) != expected:
            return True
    return False


def _has_action_to_recipient(text: str, *, recipient: str, verb_key: str) -> bool:
    preposition_match = re.search(
        rf"\b(?:{_verb_forms(verb_key)})\b.{{0,140}}\b(?:to|for)\s+"
        rf"{_label_pattern(recipient)}",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if preposition_match is not None:
        return True
    if verb_key != "recommend":
        return False
    return bool(
        re.search(
            rf"\b(?:{_russian_recommendation_forms()})\b\s+{_label_pattern(recipient)}",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )


def _recipient_acts_to_other(text: str, *, recipient: str, verb_key: str) -> bool:
    pattern = re.compile(
        rf"{_label_pattern(recipient)}(?P<gap>.{{0,80}}?)\b(?:{_verb_forms(verb_key)})\b"
        rf".{{0,140}}\b(?:to|for)\s+(?P<other>{_LABEL_RE})\b",
        re.IGNORECASE | re.DOTALL,
    )
    recipient_key = _normalized_label(recipient)
    for match in pattern.finditer(text):
        if _reported_subject_shift_before_action(match.group("gap")):
            continue
        other = _clean_label(match.group("other"))
        if other and _normalized_label(other) != recipient_key:
            return True
    if verb_key == "recommend":
        russian_direct_pattern = re.compile(
            rf"{_label_pattern(recipient)}(?P<gap>.{{0,80}}?)"
            rf"\b(?:{_russian_recommendation_forms()})\b\s+(?P<other>{_LABEL_RE})\b",
            re.IGNORECASE | re.DOTALL,
        )
        for match in russian_direct_pattern.finditer(text):
            if _reported_subject_shift_before_action(match.group("gap")):
                continue
            other = _clean_label(match.group("other"))
            if other and _normalized_label(other) != recipient_key:
                return True
    return False


def _canonical_verb_key(value: str) -> str:
    token = value.casefold()
    if token.startswith(("recommend", "suggest", "рекоменд", "порекоменд", "посовет")):
        return "recommend"
    if token.startswith(("promise", "пообещ", "обещ")):
        return "promise"
    if token.startswith(("decid", "реш")):
        return "decide"
    if token.startswith(("ask", "спрос")):
        return "ask"
    if token.startswith(("assign", "назнач")):
        return "assign"
    if token.startswith(("approv", "одобр")):
        return "approve"
    if token in {"send", "sent"}:
        return "send"
    if token in {"give", "gave"}:
        return "give"
    if token in {"tell", "told"} or token.startswith("сказ"):
        return "tell"
    return ""


def _canonical_nominal_action(value: str) -> str:
    token = value.casefold()
    if token == "decision":
        return "decide"
    if token == "promise":
        return "promise"
    if token in {"recommendation", "suggestion"}:
        return "recommend"
    return ""


def _recipient_in_tail(tail: str) -> str:
    match = re.search(
        rf"\b(?:to|for)\s+(?P<recipient>{_QUERY_LABEL_RE})\b",
        tail,
        flags=re.IGNORECASE,
    )
    if match is None:
        return ""
    return _clean_label(match.group("recipient"))


def _recipient_after_action(query: str, *, match_end: int, verb_key: str) -> str:
    tail = query[match_end : match_end + 120]
    preposition_match = re.search(
        rf"\b(?:to|for)\s+(?P<recipient>{_QUERY_LABEL_RE})\b",
        tail,
        flags=re.IGNORECASE,
    )
    if preposition_match is not None:
        return _clean_label(preposition_match.group("recipient"))
    if verb_key not in _DIRECT_RECIPIENT_VERBS:
        return ""
    direct_match = re.match(
        rf"\s+(?P<recipient>{_QUERY_LABEL_RE})\b",
        tail,
        flags=re.IGNORECASE,
    )
    if direct_match is None:
        return ""
    recipient = _clean_label(direct_match.group("recipient"))
    if not _looks_like_direct_recipient(recipient):
        return ""
    return recipient


def _verb_forms(verb_key: str) -> str:
    forms = {
        "recommend": (
            r"recommend(?:ed|s|ing)?|suggest(?:ed|s|ing)?|"
            r"made\s+(?:a\s+|the\s+)?(?:recommendation|suggestion)|"
            rf"{_russian_recommendation_forms()}"
        ),
        "promise": (
            r"promise(?:d|s|ing)?|made\s+(?:a\s+|the\s+)?promise|"
            r"пообещал(?:а)?|обещал(?:а)?"
        ),
        "decide": r"decid(?:e|ed|es|ing)|made\s+(?:a\s+|the\s+)?decision|решил(?:а)?",
        "ask": r"ask(?:ed|s|ing)?|спросил(?:а)?",
        "assign": r"assign(?:ed|s|ing)?|назначил(?:а)?",
        "approve": r"approv(?:e|ed|es|ing)|одобрил(?:а)?",
        "send": r"send|sent",
        "give": r"give|gave",
        "tell": r"tell|told|сказал(?:а)?",
    }
    return forms.get(verb_key, r"(?!x)x")


def _russian_recommendation_forms() -> str:
    return r"рекомендовал(?:а)?|порекомендовал(?:а)?|посоветовал(?:а)?"


def _label_pattern(label: str) -> str:
    return rf"(?<!\w){re.escape(label)}(?!\w)"


def _clean_label(value: str) -> str:
    label = (value or "").strip(" :,.!?;")
    if not label:
        return ""
    if _normalized_label(label) in _TEXT_LABEL_STOP_WORDS:
        return ""
    return label


def _looks_like_direct_recipient(label: str) -> bool:
    if not label:
        return False
    if label[:1].isupper():
        return True
    return _normalized_label(label) not in _DIRECT_RECIPIENT_OBJECT_STOP_WORDS


def _normalized_label(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())
