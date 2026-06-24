"""Deterministic decomposition of compound memory queries."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from infinity_context_core.application.context_lexical import query_terms
from infinity_context_core.application.context_query_intent import (
    QueryAnchorIntent,
    build_query_anchor_intent,
)
from infinity_context_core.application.context_query_state_transition import (
    state_transition_query_variants,
)
from infinity_context_core.application.context_query_support_role import (
    requests_support_role_fit,
    support_role_query_variants,
)
from infinity_context_core.application.context_query_workflow_intent import (
    gotcha_failure_query_variants,
    workflow_commitment_query_variants,
)
from infinity_context_core.application.context_temporal_query import (
    TemporalQueryIntent,
    build_temporal_query_intent,
)
from infinity_context_core.domain.entities import MemoryAnchorKind

_MAX_DECOMPOSITIONS = 6
_MAX_QUERY_CHARS = 220
_MAX_IDENTITY_TERMS = 4
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_CLAUSE_SPLIT_RE = re.compile(
    r"(?:[;?!]+|,\s+|\s+\b(?:and|also|then|plus|и|также|потом|затем)\b\s+)",
    re.IGNORECASE,
)
_QUESTION_STOPWORDS = frozenset(
    {
        "are",
        "can",
        "could",
        "did",
        "does",
        "how",
        "is",
        "may",
        "might",
        "should",
        "the",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "would",
        "где",
        "зачем",
        "как",
        "какая",
        "какие",
        "какой",
        "когда",
        "кто",
        "почему",
        "что",
        "куда",
        "откуда",
    }
)
_EVENT_TERMS = frozenset(
    {
        "call",
        "chat",
        "chatted",
        "conversation",
        "demo",
        "discussed",
        "dm",
        "attend",
        "attended",
        "hike",
        "hiked",
        "hikes",
        "hiking",
        "join",
        "joined",
        "launch",
        "meeting",
        "message",
        "move",
        "moved",
        "moving",
        "relocate",
        "relocated",
        "relocation",
        "participate",
        "participated",
        "review",
        "spoke",
        "sync",
        "talk",
        "talked",
        "meet",
        "met",
        "went",
        "workshop",
        "звонок",
        "созвон",
        "созванивалась",
        "созванивались",
        "созванивался",
        "чат",
        "встреча",
        "демо",
        "переписка",
        "переписке",
        "переписки",
        "перепиской",
        "переписку",
        "переписывалась",
        "переписывались",
        "переписывался",
        "говорил",
        "говорила",
        "говорили",
        "переезд",
        "переехал",
        "переехала",
        "переехали",
        "переезжал",
        "переезжала",
        "переезжали",
        "разговор",
        "ревью",
        "релиз",
        "созвона",
        "стендап",
    }
)
_RELOCATION_TERMS = frozenset(
    {
        "country",
        "from",
        "home",
        "lived",
        "move",
        "moved",
        "moving",
        "origin",
        "relocate",
        "relocated",
        "relocation",
        "where",
        "город",
        "дом",
        "жила",
        "жил",
        "жили",
        "из",
        "куда",
        "откуда",
        "переезд",
        "переехал",
        "переехала",
        "переехали",
        "переезжал",
        "переезжала",
        "переезжали",
        "страна",
    }
)
_RELOCATION_ACTION_TERMS = frozenset(
    {
        "move",
        "moved",
        "moving",
        "relocate",
        "relocated",
        "relocation",
        "переезд",
        "переехал",
        "переехала",
        "переехали",
        "переезжал",
        "переезжала",
        "переезжали",
    }
)
_RELOCATION_ORIGIN_TERMS = frozenset(
    {
        "city",
        "country",
        "from",
        "home",
        "lived",
        "origin",
        "where",
        "город",
        "дом",
        "жила",
        "жил",
        "жили",
        "из",
        "куда",
        "откуда",
        "страна",
    }
)
_NON_RELOCATION_FROM_CONTEXT_RE = re.compile(
    r"\bfrom\s+(?:[A-Za-z][A-Za-z]*(?:'s)?\s+){0,3}"
    r"(?:advice|article|book|email|message|recommendation|suggestion|story)\b",
    re.IGNORECASE,
)
_ARTIFACT_TERMS = frozenset(
    {
        "artifact",
        "attachment",
        "audio",
        "document",
        "file",
        "image",
        "photo",
        "picture",
        "recording",
        "screenshot",
        "video",
        "артефакт",
        "аудио",
        "видео",
        "вложение",
        "запись",
        "документ",
        "изображение",
        "картинка",
        "скриншот",
        "файл",
        "фото",
    }
)
_SOURCE_TERMS = frozenset(
    {
        "citation",
        "citations",
        "evidence",
        "file",
        "proof",
        "source",
        "sources",
        "доказательство",
        "источник",
        "источники",
        "файл",
    }
)
_INFERENCE_TERMS = frozenset(
    {
        "considered",
        "could",
        "infer",
        "inference",
        "likely",
        "might",
        "probably",
        "would",
        "вероятно",
        "вывод",
        "может",
        "мог",
        "могла",
        "похоже",
        "считается",
        "скорее",
    }
)
_COUNTERFACTUAL_TERMS = frozenset(
    {
        "would",
        "wouldn",
        "wouldnt",
        "бы",
    }
)
_COUNTERFACTUAL_EXPLICIT_TERMS = frozenset(
    {
        "hadn",
        "hadnt",
        "if",
        "without",
        "без",
        "если",
    }
)
_COUNTERFACTUAL_SUPPORT_TERMS = frozenset(
    {
        "accept",
        "accepted",
        "acceptance",
        "encourage",
        "encouraging",
        "help",
        "helping",
        "join",
        "joining",
        "support",
        "supportive",
        "welcome",
    }
)
_COMPARISON_TERMS = frozenset(
    {
        "between",
        "compare",
        "compared",
        "comparison",
        "interested",
        "less",
        "more",
        "prefer",
        "preference",
        "rather",
        "versus",
        "vs",
        "больше",
        "выбор",
        "интереснее",
        "лучше",
        "между",
        "меньше",
        "предпочел",
        "предпочла",
        "предпочитает",
        "сравни",
    }
)
_ATTRIBUTE_AGGREGATION_TERMS = frozenset(
    {
        "attend",
        "attended",
        "bought",
        "buy",
        "events",
        "instrument",
        "instruments",
        "items",
        "participate",
        "participated",
        "play",
        "plays",
        "share",
        "shared",
        "traits",
    }
)
_COMMONALITY_TERMS = frozenset(
    {
        "both",
        "common",
        "mutual",
        "same",
        "shared",
        "similar",
        "оба",
        "обе",
        "общ",
        "общего",
        "общие",
        "похож",
    }
)
_QUANTITY_COUNT_TERMS = frozenset(
    {
        "count",
        "counts",
        "many",
        "much",
        "number",
        "quantity",
        "total",
        "сколько",
    }
)
_TEMPORAL_ANSWER_TERMS = frozenset(
    {
        "date",
        "day",
        "time",
        "when",
        "weekday",
        "дата",
        "день",
        "когда",
        "число",
    }
)
_KNOWLEDGE_UPDATE_ENTITY_TERMS = frozenset(
    {
        "choice",
        "database",
        "decision",
        "engine",
        "model",
        "option",
        "plan",
        "policy",
        "provider",
        "service",
        "source",
        "tool",
        "вариант",
        "движок",
        "инструмент",
        "модель",
        "план",
        "политика",
        "провайдер",
        "решение",
        "сервис",
    }
)
_KNOWLEDGE_UPDATE_DECISION_TERMS = frozenset(
    {
        "choose",
        "chosen",
        "chose",
        "decide",
        "decided",
        "pick",
        "picked",
        "prefer",
        "preferred",
        "recommend",
        "recommended",
        "select",
        "selected",
        "use",
        "выбрал",
        "выбрала",
        "выбрать",
        "использовать",
        "решил",
        "решила",
        "рекомендовал",
        "рекомендовала",
    }
)
_KNOWLEDGE_UPDATE_CURRENT_STATE_TERMS = frozenset(
    {
        "active",
        "canonical",
        "current",
        "currently",
        "final",
        "latest",
        "newest",
        "recommended",
        "settled",
        "source",
        "still",
        "truth",
        "valid",
        "актуальная",
        "актуальное",
        "актуальные",
        "актуальный",
        "последнее",
        "последние",
        "последний",
        "последняя",
        "окончательн",
        "сейчас",
        "текущая",
        "текущее",
        "текущие",
        "текущий",
        "финальн",
        "финальное",
        "выбранный",
    }
)
_KNOWLEDGE_UPDATE_PROMPT_TERMS = frozenset(
    {
        "what",
        "which",
        "какая",
        "какие",
        "какой",
        "какую",
        "какое",
        "что",
    }
)
_KNOWLEDGE_UPDATE_PROMPT_ACTION_TERMS = frozenset(
    {
        "choose",
        "chosen",
        "chose",
        "pick",
        "picked",
        "select",
        "selected",
        "use",
        "выбрал",
        "выбрала",
        "выбрать",
        "использовать",
    }
)
_ACTIVITY_PARTICIPATION_TERMS = frozenset(
    {
        "activities",
        "activity",
        "hobbies",
        "hobby",
        "partake",
        "participate",
        "participates",
        "participated",
    }
)
_IDENTITY_ATTRIBUTE_TERMS = frozenset(
    {
        "gender",
        "identity",
        "pronouns",
        "trans",
        "transgender",
    }
)
_RELATIONSHIP_STATUS_TERMS = frozenset(
    {
        "breakup",
        "dating",
        "divorced",
        "married",
        "partner",
        "relationship",
        "single",
        "spouse",
        "status",
    }
)
_ACTION_ROLE_TERMS = frozenset(
    {
        "approve",
        "approved",
        "ask",
        "asked",
        "assign",
        "assigned",
        "decide",
        "decided",
        "decision",
        "give",
        "gave",
        "promise",
        "promised",
        "recommendation",
        "recommend",
        "recommended",
        "send",
        "sent",
        "suggestion",
        "tell",
        "told",
        "назначил",
        "назначила",
        "одобрил",
        "одобрила",
        "пообещал",
        "пообещала",
        "рекомендовал",
        "рекомендовала",
        "решил",
        "решила",
        "сказал",
        "сказала",
        "спросил",
        "спросила",
    }
)
_DEADLINE_TERMS = frozenset(
    {
        "deadline",
        "deadlines",
        "deliverable",
        "deliverables",
        "due",
        "milestone",
        "milestones",
        "overdue",
        "schedule",
        "scheduled",
        "target",
        "timeline",
        "upcoming",
        "дедлайн",
        "дедлайны",
        "просрочен",
        "просрочена",
        "просрочено",
        "просроченные",
        "срок",
        "сроки",
    }
)
_FOLLOWUP_TASK_TERMS = frozenset(
    {
        "action",
        "assigned",
        "assignee",
        "assignees",
        "agreed",
        "commitment",
        "commitments",
        "committed",
        "followup",
        "own",
        "owner",
        "owns",
        "promise",
        "promised",
        "promises",
        "remind",
        "reminder",
        "reminders",
        "responsibility",
        "responsible",
        "task",
        "tasks",
        "todo",
        "todos",
        "ответственный",
        "ответственная",
        "ответственные",
        "задача",
        "задачи",
        "обещал",
        "обещала",
        "назначено",
        "назначил",
        "назначила",
        "напомни",
        "напоминание",
        "напоминания",
        "поручение",
        "поручения",
    }
)
_GOTCHA_FAILURE_TERMS = frozenset(
    {
        "blocked",
        "blocker",
        "broke",
        "broken",
        "caveat",
        "caveats",
        "error",
        "errors",
        "fail",
        "failed",
        "failure",
        "failures",
        "gotcha",
        "gotchas",
        "pitfall",
        "pitfalls",
        "problem",
        "problems",
        "risk",
        "risks",
        "trap",
        "traps",
        "warning",
        "warnings",
        "workaround",
        "workarounds",
        "воркэраунд",
        "избегать",
        "камни",
        "ошибка",
        "ошибки",
        "подводные",
        "проблема",
        "проблемы",
        "риск",
        "риски",
        "сломалось",
        "сбой",
    }
)
_CURRENT_GOAL_TERMS = frozenset(
    {
        "adopt",
        "adoption",
        "back",
        "career",
        "country",
        "future",
        "goal",
        "goals",
        "move",
        "moved",
        "moving",
        "open",
        "plan",
        "pursue",
        "soon",
        "want",
        "wants",
    }
)
_SALIENT_DROP_VARIANTS = frozenset(
    {
        *_QUESTION_STOPWORDS,
        *_INFERENCE_TERMS,
        "career",
        "consider",
        "considered",
        "does",
        "option",
        "still",
    }
)
_MAX_SALIENT_TERMS = 5
_EVIDENCE_REASON_RE = re.compile(
    r"\b("
    r"why|reason|because|what evidence|which evidence|what shows|what showed|"
    r"what indicates|how do we know|how can we tell|how would we know|"
    r"почему|причин|потому что|какие доказательства|какое доказательство|"
    r"что показывает|что показало|как мы знаем|откуда известно"
    r")\b",
    re.IGNORECASE,
)
_ABSENCE_CONTRAST_RE = re.compile(
    r"\b(?:instead\s+of|rather\s+than|without)\b|"
    r"\b(?:did\s+not|didn'?t|never|not)\s+"
    r"(?:mention|mentioned|say|said|discuss|discussed)\b|"
    r"\b(?:не\s+упоминал\w*|не\s+говорил\w*|вместо|без)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class QueryDecomposition:
    query: str
    reason: str


@dataclass(frozen=True)
class QueryDecompositionPlan:
    original_query: str
    decompositions: tuple[QueryDecomposition, ...]

    @property
    def empty(self) -> bool:
        return not self.decompositions

    def diagnostics(self) -> dict[str, object]:
        return {
            "query_decomposition_status": "empty" if self.empty else "available",
            "query_decomposition_count": len(self.decompositions),
            "query_decomposition_reasons": [item.reason for item in self.decompositions],
        }


def build_query_decomposition_plan(
    query: str,
    *,
    anchor_intent: QueryAnchorIntent | None = None,
    temporal_intent: TemporalQueryIntent | None = None,
) -> QueryDecompositionPlan:
    normalized_query = _normalize_query(query)
    if not normalized_query:
        return QueryDecompositionPlan(original_query=query, decompositions=())
    anchor_intent = anchor_intent or build_query_anchor_intent(query)
    temporal_intent = temporal_intent or build_temporal_query_intent(query)
    variants = _query_variant_set(query)
    variants = frozenset(
        (
            *variants,
            *gotcha_failure_query_variants(query),
            *state_transition_query_variants(query),
            *support_role_query_variants(query),
            *workflow_commitment_query_variants(query),
        )
    )
    raw_tokens = frozenset(_raw_query_tokens(query))
    identities = _identity_terms(query, anchor_intent)
    salient_terms = _salient_terms(query, identities=identities)
    requests_relocation_context = _requests_relocation_context(
        query=normalized_query,
        variants=variants,
    )
    requests_relocation_destination_context = _requests_relocation_destination_context(
        variants=variants,
    )
    candidates: list[QueryDecomposition] = []
    _append_clause_decompositions(candidates, query=query, identities=identities)
    if _has_event_focus(anchor_intent, variants) and not (
        requests_relocation_context or requests_relocation_destination_context
    ):
        _append_candidate(
            candidates,
            query=_compose_query(
                identities,
                (
                    "event conversation meeting call chat message dm transcript "
                    "notes discussed mentioned decision action item follow up"
                ),
            ),
            reason="decomposition_event_context",
        )
    if _requests_lgbtq_event_slot_aggregation(variants):
        _append_candidate(
            candidates,
            query=_compose_query(
                identities,
                (
                    "lgbtq pride parade pride march went attended participated "
                    "rainbow flags community belonged accepted happy equality"
                ),
            ),
            reason="decomposition_lgbtq_pride_event",
        )
        _append_candidate(
            candidates,
            query=_compose_query(
                identities,
                (
                    "lgbtq support group attended went transgender stories powerful "
                    "inspiring accepted courage embrace community"
                ),
            ),
            reason="decomposition_lgbtq_support_group_event",
        )
        _append_candidate(
            candidates,
            query=_compose_query(
                identities,
                (
                    "school event speech talk spoke gave transgender journey students "
                    "involved lgbtq community awareness inclusion"
                ),
            ),
            reason="decomposition_lgbtq_school_speech_event",
        )
    if requests_relocation_destination_context:
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "relocation moved move relocated to destination new current "
                    "home country city settled lives now timeline"
                ),
            ),
            reason="decomposition_relocation_destination",
        )
    if requests_relocation_context:
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "relocation moved move relocated from origin previous home "
                    "country city lived before timeline"
                ),
            ),
            reason="decomposition_relocation_context",
        )
    if temporal_intent.requests_change:
        _append_candidate(
            candidates,
            query=_compose_query(
                identities,
                (
                    "changed updated current previous before after superseded "
                    "replaced difference decision"
                ),
            ),
            reason="decomposition_temporal_change",
        )
    if _requests_state_transition_context(variants=variants):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "state transition changed switched replaced migrated from to "
                    "previous old current new active final selected superseded "
                    "no longer valid replacement replaced by before after"
                ),
            ),
            reason="decomposition_state_transition",
        )
    if temporal_intent.after_event or temporal_intent.before_event:
        _append_candidate(
            candidates,
            query=_compose_query(
                identities,
                _event_sequence_tail(temporal_intent),
            ),
            reason="decomposition_event_sequence",
        )
    if temporal_intent.relative_time_hints:
        _append_candidate(
            candidates,
            query=_compose_query(
                identities,
                (
                    "event temporal time window occurred capture transcript "
                    "notes meeting call chat message "
                    f"{' '.join(temporal_intent.relative_time_hints)}"
                ),
            ),
            reason="decomposition_relative_time",
        )
    if _requests_knowledge_update_current(
        variants=variants,
        temporal_intent=temporal_intent,
    ):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "current latest active final decided chose selected switched "
                    "recommended preferred should use provider tool model option "
                    "engine database service retrieval valid not stale superseded old"
                ),
            ),
            reason="decomposition_knowledge_update_current",
        )
    if _requests_knowledge_update_previous(
        query=normalized_query,
        variants=variants,
        temporal_intent=temporal_intent,
    ):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "previous old stale outdated superseded no longer valid "
                    "not current replaced deprecated expired before review"
                ),
            ),
            reason="decomposition_knowledge_update_previous",
        )
    if variants.intersection(_TEMPORAL_ANSWER_TERMS):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "when date day time session date weekday monday tuesday "
                    "wednesday thursday friday saturday sunday calendar occurred"
                ),
            ),
            reason="decomposition_temporal_answer",
        )
    if variants.intersection(_ARTIFACT_TERMS):
        _append_candidate(
            candidates,
            query=_compose_query(
                identities,
                (
                    "artifact file screenshot image video audio document ocr "
                    "transcript detected text keyframe source"
                ),
            ),
            reason="decomposition_artifact_evidence",
        )
    if variants.intersection(_SOURCE_TERMS):
        _append_candidate(
            candidates,
            query=_compose_query(
                identities,
                "source citation evidence file artifact reference provenance",
            ),
            reason="decomposition_source_evidence",
        )
    if _requests_evidence_reason(query):
        _append_candidate(
            candidates,
            query=_compose_query(
                identities,
                (
                    "reason evidence because observed mentioned showed indicates "
                    "supporting fact source citation quote explanation why"
                ),
            ),
            reason="decomposition_evidence_reason",
        )
    if _requests_gotcha_failure_context(variants=variants):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "gotcha pitfall caveat known issue known problem failure "
                    "failed error broke blocked blocker risk warning workaround "
                    "root cause troubleshooting avoid do not repeat next time "
                    "prerequisite limitation trap"
                ),
            ),
            reason="decomposition_gotcha_failure",
        )
    if _requests_absence_contrast(query):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "mentioned did not mention absent instead rather than without "
                    "contrast alternative named pet cat dog hamster evidence"
                ),
            ),
            reason="decomposition_absence_contrast",
        )
    if raw_tokens.intersection(_IDENTITY_ATTRIBUTE_TERMS):
        _append_candidate(
            candidates,
            query=_compose_query(
                identities,
                (
                    "identity gender pronouns transgender trans woman transition "
                    "true self accepted belongs community support group pride"
                ),
            ),
            reason="decomposition_identity_attribute",
        )
    if _requests_relationship_status(variants):
        _append_candidate(
            candidates,
            query=_compose_query(
                identities,
                (
                    "relationship status single parent partner spouse married "
                    "dating breakup friends family mentors support system kids "
                    "children challenge make family"
                ),
            ),
            reason="decomposition_relationship_status",
        )
    if variants.intersection(_ACTION_ROLE_TERMS):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "decision decided promised promise recommendation recommended "
                    "asked assigned approved sent gave told actor recipient speaker "
                    "dialogue quote transcript outcome commitment next step"
                ),
            ),
            reason="decomposition_action_role",
        )
    if variants.intersection(_DEADLINE_TERMS):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "deadline due date target date schedule milestone timeline "
                    "deliverable overdue upcoming commitment action item follow up "
                    "meeting call decision promised agreed"
                ),
            ),
            reason="decomposition_deadline_commitment",
        )
    if _requests_followup_task_context(raw_tokens=raw_tokens, variants=variants):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "action item task todo follow up next step reminder assigned "
                    "owner responsible assignee commitment promised due date deadline "
                    "meeting call decision status"
                ),
            ),
            reason="decomposition_followup_task",
        )
    if _requests_counterfactual_evidence(raw_tokens=raw_tokens, variants=variants):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "counterfactual hypothetical would likely past behavior "
                    "preference trait supporting evidence observed mentioned "
                    "enjoyed disliked avoided interested supportive acceptance "
                    "similar situation"
                ),
            ),
            reason="decomposition_counterfactual_evidence",
        )
    if requests_support_role_fit(raw_tokens=raw_tokens, variants=variants):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "support role fit mentor mentoring guidance advice coach "
                    "volunteer counseling counselor listened comfort empathy "
                    "patient helped accepted safe trust similar issues reliable "
                    "responsible care"
                ),
            ),
            reason="decomposition_support_role_fit",
        )
    if variants.intersection(_INFERENCE_TERMS):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "inference supporting evidence likely would considered "
                    "observed mentioned indicates preference trait decision reason "
                    "support supportive encouraging acceptance care help"
                ),
            ),
            reason="decomposition_inference_support",
        )
        if _requests_inference_current_preference_or_goal(
            raw_tokens=raw_tokens,
            variants=variants,
        ):
            _append_candidate(
                candidates,
                query=_compose_query(
                    (*identities, *salient_terms),
                    (
                        "current goal future plan career option counseling counselor "
                        "mental health jobs next steps figure out wants preference "
                        "likes dislikes interested recently now decided committed "
                        "adoption family children kids home roof agency interview "
                        "build career activity service country office military"
                    ),
                ),
                reason="decomposition_current_preference_or_goal",
            )
    if _requests_non_inference_career_goal(raw_tokens=raw_tokens, variants=variants):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "current career path goal decided pursue education options "
                    "counseling counselor mental health jobs work career option "
                    "next steps figure out looking into"
                ),
            ),
            reason="decomposition_current_preference_or_goal",
        )
    if _requests_comparison_preference(raw_tokens=raw_tokens, variants=variants):
        _append_candidate(
            candidates,
            query=_compose_query(
                identities,
                (
                    "comparison preference choice option alternative likes dislikes "
                    "interested more less rather prefer similar difference evidence"
                ),
            ),
            reason="decomposition_comparison_preference",
        )
    if _requests_activity_participation(raw_tokens=raw_tokens, variants=variants):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "activities hobbies activity partake participate observed "
                    "painting swimming swim pottery class camping running creative "
                    "outdoors exercise family kids fam weekend unplug hang therapy "
                    "therapeutic photo picture image visual query take look"
                ),
            ),
            reason="decomposition_activity_participation",
        )
    if _requests_commonality_context(identities=identities, variants=variants):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "common shared both mutual same similar overlap interests hobbies "
                    "activities enjoy like love prefer painting camping hiking music "
                    "books games food art evidence"
                ),
            ),
            reason="decomposition_commonality",
        )
    if variants.intersection(_QUANTITY_COUNT_TERMS):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                (
                    "count number total quantity amount many much times "
                    "one two three four five six seven eight nine ten "
                    "once twice couple several multiple"
                ),
            ),
            reason="decomposition_quantity_count",
        )
    if variants.intersection(_ATTRIBUTE_AGGREGATION_TERMS):
        _append_candidate(
            candidates,
            query=_compose_query(
                (*identities, *salient_terms),
                _attribute_aggregation_tail(variants),
            ),
            reason="decomposition_attribute_aggregation",
        )
    return QueryDecompositionPlan(
        original_query=query,
        decompositions=tuple(candidates[:_MAX_DECOMPOSITIONS]),
    )


def _append_clause_decompositions(
    candidates: list[QueryDecomposition],
    *,
    query: str,
    identities: tuple[str, ...],
) -> None:
    normalized_query_key = _query_dedupe_key(query)
    for raw_clause in _CLAUSE_SPLIT_RE.split(query):
        clause = _clean_clause_query(raw_clause)
        if not _is_useful_clause(clause):
            continue
        clause_query = _with_missing_identities(clause, identities)
        if _query_dedupe_key(clause_query) == normalized_query_key:
            continue
        _append_candidate(
            candidates,
            query=clause_query,
            reason="decomposition_clause",
        )


def _append_candidate(
    candidates: list[QueryDecomposition],
    *,
    query: str,
    reason: str,
) -> None:
    normalized_query = _normalize_query(query)
    if not normalized_query:
        return
    key = _query_dedupe_key(normalized_query)
    if any(
        _query_dedupe_key(item.query) == key
        or (item.reason == reason and reason != "decomposition_clause")
        for item in candidates
    ):
        return
    candidates.append(
        QueryDecomposition(
            query=normalized_query[:_MAX_QUERY_CHARS].strip(),
            reason=reason,
        )
    )


def _has_event_focus(
    anchor_intent: QueryAnchorIntent,
    variants: frozenset[str],
) -> bool:
    return bool(
        variants.intersection(_EVENT_TERMS)
        or anchor_intent.keys_for_kind(MemoryAnchorKind.EVENT)
        or anchor_intent.event_type_keys()
    )


def _requests_lgbtq_event_slot_aggregation(variants: frozenset[str]) -> bool:
    return bool(
        variants.intersection({"lgbtq", "queer"})
        and variants.intersection(
            {"event", "events", "attend", "attended", "participate", "participated"}
        )
    )


def _compose_query(
    identities: Sequence[str],
    tail: str,
) -> str:
    return _normalize_query(" ".join((*identities, tail)))


def _salient_terms(query: str, *, identities: tuple[str, ...]) -> tuple[str, ...]:
    identity_keys = {identity.casefold() for identity in identities}
    terms: list[str] = []
    seen: set[str] = set()
    for term in query_terms(query, min_chars=3, max_terms=18):
        variants = frozenset(term.variants)
        raw = _normalize_identity_term(term.raw)
        if not raw:
            continue
        key = raw.casefold()
        if key in seen or key in identity_keys:
            continue
        if variants.intersection(_SALIENT_DROP_VARIANTS):
            continue
        terms.append(raw)
        seen.add(key)
        if len(terms) >= _MAX_SALIENT_TERMS:
            break
    return tuple(terms)


def _attribute_aggregation_tail(variants: frozenset[str]) -> str:
    tails: list[str] = [
        "aggregate list multiple mentions evidence observed mentioned",
    ]
    if variants.intersection({"items", "bought", "buy"}):
        tails.append("item bought purchased got new gift object possession")
    if variants.intersection({"instrument", "instruments", "play", "plays"}):
        tails.append("instrument music play plays played violin clarinet piano guitar")
    if variants.intersection({"events", "attend", "attended", "participate", "participated"}):
        tails.append(
            "event attended participated went conference parade speech support group "
            "reading meeting mentorship mentoring youth children school talk gender "
            "identity inclusion community ally allies"
        )
    if variants.intersection({"share", "shared"}):
        tails.append(
            "shared both similar interests hobbies enjoy watching movies making "
            "desserts recipes baking"
        )
    if variants.intersection(_COMMONALITY_TERMS):
        tails.append(
            "common shared both mutual same similar overlap interests hobbies "
            "activities enjoy like love prefer painting camping hiking music books games"
        )
    if variants.intersection({"traits"}):
        tails.append(
            "trait personality thoughtful authentic driven caring supportive concerned helpful"
        )
    return _normalize_query(" ".join(tails))


def _requests_non_inference_career_goal(
    *,
    raw_tokens: frozenset[str],
    variants: frozenset[str],
) -> bool:
    return "career" in variants and bool(
        raw_tokens.intersection({"decided", "persue"}) or "path" in variants
    )


def _requests_inference_current_preference_or_goal(
    *,
    raw_tokens: frozenset[str],
    variants: frozenset[str],
) -> bool:
    if raw_tokens.intersection(_CURRENT_GOAL_TERMS):
        return True
    return bool("career" in variants and raw_tokens.intersection({"option", "path", "pursue"}))


def _requests_comparison_preference(
    *,
    raw_tokens: frozenset[str],
    variants: frozenset[str],
) -> bool:
    if raw_tokens.intersection(_COMPARISON_TERMS):
        return True
    return bool({"or", "option"}.issubset(raw_tokens) and variants.intersection({"prefer"}))


def _requests_counterfactual_evidence(
    *,
    raw_tokens: frozenset[str],
    variants: frozenset[str],
) -> bool:
    if raw_tokens.intersection(_COUNTERFACTUAL_EXPLICIT_TERMS):
        return True
    if variants.intersection({"would", "wouldnt"}) or raw_tokens.intersection(
        {"would", "wouldn", "wouldnt"}
    ):
        return bool(variants.intersection(_COUNTERFACTUAL_SUPPORT_TERMS))
    return bool("бы" in raw_tokens and variants.intersection({"мог", "могла", "может"}))


def _event_sequence_tail(intent: TemporalQueryIntent) -> str:
    if intent.after_event and not intent.before_event:
        return (
            "after following later next timeline outcome follow up decision "
            "result happened then response meeting call chat message conversation event"
        )
    if intent.before_event and not intent.after_event:
        return (
            "before earlier prior previous timeline context lead up reason "
            "setup happened meeting call chat message conversation event"
        )
    return (
        "before after timeline sequence earlier later prior next meeting call chat message "
        "conversation event outcome context"
    )


def _requests_evidence_reason(query: str) -> bool:
    return bool(_EVIDENCE_REASON_RE.search(query))


def _requests_knowledge_update_current(
    *,
    variants: frozenset[str],
    temporal_intent: TemporalQueryIntent,
) -> bool:
    if (
        temporal_intent.after_event
        or temporal_intent.before_event
        or temporal_intent.relative_time_hints
        or temporal_intent.requests_previous
    ):
        return False
    if variants.intersection(_KNOWLEDGE_UPDATE_ENTITY_TERMS) and variants.intersection(
        _KNOWLEDGE_UPDATE_CURRENT_STATE_TERMS
    ):
        return True
    if not variants.intersection(_KNOWLEDGE_UPDATE_DECISION_TERMS):
        return False
    if variants.intersection(_KNOWLEDGE_UPDATE_ENTITY_TERMS):
        return True
    return bool(
        variants.intersection(_KNOWLEDGE_UPDATE_PROMPT_TERMS)
        and variants.intersection(_KNOWLEDGE_UPDATE_PROMPT_ACTION_TERMS)
    )


def _requests_knowledge_update_previous(
    *,
    query: str,
    variants: frozenset[str],
    temporal_intent: TemporalQueryIntent,
) -> bool:
    if not temporal_intent.requests_previous:
        return False
    if "no longer" in query or "not current" in query:
        return True
    return bool(
        variants.intersection(
            {
                "anymore",
                "больше",
                "longer",
                "stopped",
                "перестал",
                "перестала",
                "перестали",
            }
        )
    )


def _requests_absence_contrast(query: str) -> bool:
    return bool(_ABSENCE_CONTRAST_RE.search(query))


def _requests_relationship_status(variants: frozenset[str]) -> bool:
    if {"relationship", "status"}.issubset(variants):
        return True
    return bool(
        variants.intersection({"single", "married", "dating", "partner", "spouse"})
        and variants.intersection(_RELATIONSHIP_STATUS_TERMS)
    )


def _requests_activity_participation(
    *,
    raw_tokens: frozenset[str],
    variants: frozenset[str],
) -> bool:
    if not variants.intersection({"activity", "hobby"}):
        return False
    return bool(raw_tokens.intersection(_ACTIVITY_PARTICIPATION_TERMS))


def _requests_commonality_context(
    *,
    identities: tuple[str, ...],
    variants: frozenset[str],
) -> bool:
    return len(identities) >= 2 and bool(variants.intersection(_COMMONALITY_TERMS))


def _requests_followup_task_context(
    *,
    raw_tokens: frozenset[str],
    variants: frozenset[str],
) -> bool:
    if "workflow_commitment_request" in variants:
        return True
    if {"action", "item"}.issubset(variants) or {"follow", "up"}.issubset(raw_tokens):
        return True
    return bool(variants.intersection(_FOLLOWUP_TASK_TERMS))


def _requests_gotcha_failure_context(*, variants: frozenset[str]) -> bool:
    if "gotcha_failure_request" in variants:
        return True
    if {"known", "issue"}.issubset(variants) or {"known", "problem"}.issubset(variants):
        return True
    return bool(variants.intersection(_GOTCHA_FAILURE_TERMS))


def _requests_state_transition_context(*, variants: frozenset[str]) -> bool:
    return "state_transition_request" in variants


def _requests_relocation_context(*, query: str, variants: frozenset[str]) -> bool:
    if not variants.intersection(_RELOCATION_TERMS):
        return False
    if _NON_RELOCATION_FROM_CONTEXT_RE.search(query):
        return False
    if _requests_relocation_destination_only(variants=variants):
        return False
    if variants.intersection(_RELOCATION_ACTION_TERMS):
        return True
    if "откуда" in variants:
        return True
    origin_terms = variants.intersection(_RELOCATION_ORIGIN_TERMS)
    if {"where", "from"}.issubset(origin_terms):
        return True
    if origin_terms.intersection({"home", "country", "lived", "origin", "city"}):
        return True
    return bool(origin_terms.intersection({"дом", "жила", "жил", "жили", "город", "страна"}))


def _requests_relocation_destination_only(*, variants: frozenset[str]) -> bool:
    if not variants.intersection(_RELOCATION_ACTION_TERMS):
        return False
    if variants.intersection({"from", "откуда", "из"}):
        return False
    return _requests_relocation_destination_context(variants=variants)


def _requests_relocation_destination_context(*, variants: frozenset[str]) -> bool:
    if not variants.intersection(_RELOCATION_ACTION_TERMS):
        return False
    if "куда" in variants:
        return True
    return bool({"where", "to"}.issubset(variants))


def _with_missing_identities(clause: str, identities: tuple[str, ...]) -> str:
    if not identities:
        return clause
    clause_key = clause.casefold()
    if _clause_contains_identity(clause_key, identities):
        return clause
    missing = tuple(
        identity for identity in identities[:2] if identity.casefold() not in clause_key
    )
    if not missing:
        return clause
    return _normalize_query(" ".join((*missing, clause)))


def _clause_contains_identity(clause_key: str, identities: tuple[str, ...]) -> bool:
    return any(
        re.search(rf"(?<!\w){re.escape(identity.casefold())}(?!\w)", clause_key)
        for identity in identities
        if identity
    )


def _identity_terms(
    query: str,
    anchor_intent: QueryAnchorIntent,
) -> tuple[str, ...]:
    labels = [
        hint.label
        for hint in anchor_intent.hints
        if hint.kind
        in {
            MemoryAnchorKind.PERSON,
            MemoryAnchorKind.PROJECT,
            MemoryAnchorKind.ORGANIZATION,
        }
    ]
    labels.extend(_capitalized_identity_terms(query))
    deduped: list[str] = []
    seen: set[str] = set()
    for label in labels:
        term = _normalize_identity_term(label)
        if not term:
            continue
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(term)
        if len(deduped) >= _MAX_IDENTITY_TERMS:
            break
    return tuple(deduped)


def _capitalized_identity_terms(query: str) -> Iterable[str]:
    for match in _TOKEN_RE.finditer(query):
        token = match.group(0).strip("_")
        if len(token) < 2 or token.casefold() in _QUESTION_STOPWORDS:
            continue
        if token[:1].isupper():
            yield token


def _normalize_identity_term(value: str) -> str:
    tokens = _normalize_query(value).strip("@").split()
    while tokens and tokens[0].casefold() in _QUESTION_STOPWORDS:
        tokens = tokens[1:]
    while tokens and tokens[-1].casefold() in _QUESTION_STOPWORDS:
        tokens = tokens[:-1]
    token = _normalize_query(" ".join(tokens)).strip("@")
    if len(token) < 2 or token.casefold() in _QUESTION_STOPWORDS:
        return ""
    return token


def _is_useful_clause(clause: str) -> bool:
    if len(clause) < 8:
        return False
    terms = query_terms(clause, min_chars=2, max_terms=12)
    distinctive = [
        term for term in terms if not set(term.variants).intersection(_QUESTION_STOPWORDS)
    ]
    return len(distinctive) >= 2


def _query_variant_set(query: str) -> frozenset[str]:
    variants: set[str] = set()
    for term in query_terms(query, min_chars=2, max_terms=32):
        variants.update(term.variants)
    variants.update(_raw_query_tokens(query))
    return frozenset(variants)


def _raw_query_tokens(query: str) -> Iterable[str]:
    for match in _TOKEN_RE.finditer(query):
        token = match.group(0).casefold().strip("_")
        if len(token) >= 2:
            yield token


def _normalize_query(query: str) -> str:
    return " ".join(query.split())


def _clean_clause_query(query: str) -> str:
    normalized = _normalize_query(query)
    return re.sub(
        r"^(?:and|also|then|plus|и|также|потом|затем)\s+",
        "",
        normalized,
        flags=re.IGNORECASE,
    )


def _query_dedupe_key(query: str) -> str:
    return _normalize_query(query).strip(" \t\r\n.,;:!?").casefold()
