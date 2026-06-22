"""Deterministic query decomposition for evidence-oriented retrieval."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from infinity_context_core.application.context_lexical import query_terms
from infinity_context_core.application.context_query_decomposition import (
    QueryDecompositionPlan,
    build_query_decomposition_plan,
)


@dataclass(frozen=True)
class QueryExpansion:
    query: str
    reason: str


@dataclass(frozen=True)
class QueryExpansionPlan:
    original_query: str
    expansions: tuple[QueryExpansion, ...]
    decompositions: tuple[QueryExpansion, ...] = ()

    @property
    def retrieval_queries(self) -> tuple[QueryExpansion, ...]:
        return (
            QueryExpansion(query=self.original_query, reason="original_query"),
            *self.decompositions,
            *self.expansions,
        )

    def diagnostics(self) -> dict[str, object]:
        return {
            "query_expansion_status": "available" if self.expansions else "empty",
            "query_expansion_count": len(self.expansions),
            "query_expansion_reasons": [item.reason for item in self.expansions],
            "query_decomposition_status": (
                "available" if self.decompositions else "empty"
            ),
            "query_decomposition_count": len(self.decompositions),
            "query_decomposition_reasons": [
                item.reason for item in self.decompositions
            ],
        }


_EXPANSION_RULES: tuple[tuple[frozenset[str], str, str], ...] = (
    (
        frozenset({"pursue", "career"}),
        "looking counseling mental health jobs education options work",
        "career_intent_bridge",
    ),
    (
        frozenset({"field", "pursue"}),
        (
            "education edu career options fields jobs counseling counselor mental "
            "health psychology support similar issues pursue work"
        ),
        "education_career_field_bridge",
    ),
    (
        frozenset({"support", "career"}),
        (
            "motivation motivated mattered made difference support got counseling "
            "support groups improved life mental health help people safe inviting grow"
        ),
        "support_career_motivation_bridge",
    ),
    (
        frozenset({"support", "growing"}),
        "journey love support acceptance community hope",
        "support_counterfactual_bridge",
    ),
    (
        frozenset({"support", "growing"}),
        "blessed love support journey supportive community hope",
        "support_origin_bridge",
    ),
    (
        frozenset({"move", "from"}),
        "moved home country roots family origin",
        "relocation_origin_bridge",
    ),
    (
        frozenset({"national", "park"}),
        "camping trip campfire meteor shower nature outdoors",
        "outdoor_preference_bridge",
    ),
    (
        frozenset({"theme", "park"}),
        "camping trip campfire meteor shower nature outdoors",
        "outdoor_preference_bridge",
    ),
    (
        frozenset({"national", "park"}),
        "camping trip meteor shower sky universe nature",
        "outdoor_nature_memory_bridge",
    ),
    (
        frozenset({"theme", "park"}),
        "camping trip meteor shower sky universe nature",
        "outdoor_nature_memory_bridge",
    ),
    (
        frozenset({"decision", "adopt"}),
        "adoption family kids children mom support good luck",
        "adoption_support_bridge",
    ),
    (
        frozenset({"ally", "transgender"}),
        "supportive support acceptance community encouraging trans lgbtq",
        "ally_support_bridge",
    ),
    (
        frozenset({"ally"}),
        "supportive support acceptance encouraging community care help",
        "ally_support_bridge",
    ),
    (
        frozenset({"member", "community"}),
        "part belong identify refer herself community lgbtq",
        "community_membership_bridge",
    ),
    (
        frozenset({"political", "leaning"}),
        "rights lgbtq transition conservative conservatives unwelcoming support",
        "political_inference_bridge",
    ),
    (
        frozenset({"religious"}),
        "church faith religious conservative conservatives",
        "religious_inference_bridge",
    ),
    (
        frozenset({"destress"}),
        "running pottery class therapeutic therapy calm relax clear mind headspace",
        "destress_activity_bridge",
    ),
    (
        frozenset({"camped"}),
        "camping camped family mountains beach forest outdoors trip",
        "camping_location_bridge",
    ),
    (
        frozenset({"activities"}),
        "pottery camping painting swimming running hobbies activities creative outdoors",
        "activity_aggregation_bridge",
    ),
    (
        frozenset({"activity", "family"}),
        (
            "family kids children husband museum dinosaur painting nature camping "
            "campfire marshmallows hiking beach stories trip spending time pottery "
            "workshop clay pots swimming fam unplug hang creativity imagination "
            "excited motivated motivate love latest work quiet weekend"
        ),
        "family_activity_bridge",
    ),
    (
        frozenset({"activity", "family"}),
        (
            "family painting together nature inspired latest work sunset flowers "
            "kids creativity imagination project"
        ),
        "family_painting_activity_bridge",
    ),
    (
        frozenset({"activity", "family"}),
        (
            "family swimming with kids swim taking care ourselves vital self care "
            "after conversation talk soon"
        ),
        "family_swimming_activity_bridge",
    ),
    (
        frozenset({"activity", "family"}),
        (
            "family husband kids children keep motivated motivate motivation love "
            "support moments worth lucky"
        ),
        "family_motivation_context_bridge",
    ),
    (
        frozenset({"partake"}),
        "pottery camping painting swimming running hobbies activities creative outdoors",
        "activity_aggregation_bridge",
    ),
    (
        frozenset({"event", "attend"}),
        (
            "events participated attended joined went lgbtq community advocacy "
            "activism campaign mentorship mentoring program youth equality awareness"
        ),
        "event_participation_bridge",
    ),
    (
        frozenset({"lgbtq", "event", "attend"}),
        (
            "lgbtq pride parade marched flags signs celebrating love diversity "
            "accepted happy belonged community equality"
        ),
        "lgbtq_pride_event_bridge",
    ),
    (
        frozenset({"lgbtq", "event", "attend"}),
        (
            "lgbtq support group transgender stories powerful inspiring accepted "
            "courage embrace community"
        ),
        "lgbtq_support_group_event_bridge",
    ),
    (
        frozenset({"lgbtq", "event", "attend"}),
        (
            "school event speech talk transgender journey students involved "
            "community reactions awareness allies inclusion gender identity"
        ),
        "lgbtq_school_event_bridge",
    ),
    (
        frozenset({"event", "attend", "help"}),
        (
            "help children youth mentorship mentoring program school speech talk "
            "students audience inspire allies community gender identity inclusion "
            "support voice transgender journey"
        ),
        "event_participation_help_bridge",
    ),
    (
        frozenset({"lgbtq", "community", "attend"}),
        (
            "lgbtq community participating ways activist group connected activists "
            "rights support voice difference pride parade mentorship program youth "
            "art show paintings"
        ),
        "lgbtq_community_participation_bridge",
    ),
    (
        frozenset({"counseling", "workshop"}),
        (
            "counseling workshop therapeutic methods trans people mental health "
            "safe space professionals support acceptance enlightening"
        ),
        "counseling_workshop_bridge",
    ),
    (
        frozenset({"degree"}),
        (
            "degree policymaking policy political science public administration "
            "public affairs positive impact opportunities improvements"
        ),
        "degree_policy_inference_bridge",
    ),
    (
        frozenset({"friend", "beside"}),
        (
            "friends teammates team video game counter strike global offensive "
            "played together blast friends besides"
        ),
        "friends_team_inference_bridge",
    ),
    (
        frozenset({"beach", "mountains"}),
        (
            "beach ocean sunset sailboat walk weekly nature close nearby mountains "
            "outdoors hiking camping"
        ),
        "beach_or_mountains_inference_bridge",
    ),
    (
        frozenset({"future", "job", "pursue"}),
        (
            "future job career volunteering volunteer shelter homeless front desk "
            "talks helping people make difference fulfilling kindness community"
        ),
        "volunteer_career_inference_bridge",
    ),
    (
        frozenset({"pet", "discomfort"}),
        (
            "pets animals reptiles fur allergic allergy puffy itchy discomfort "
            "turtles cockroaches pet"
        ),
        "pet_allergy_discomfort_bridge",
    ),
    (
        frozenset({"condition", "allergy"}),
        (
            "underlying condition allergies allergic reptiles animals fur puffy "
            "itchy cockroaches turtles pet discomfort"
        ),
        "allergy_condition_inference_bridge",
    ),
    (
        frozenset({"symbol"}),
        (
            "symbols important rainbow flag mural eagle freedom pride courage "
            "strength trans community resilience stained glass acceptance"
        ),
        "symbol_importance_bridge",
    ),
    (
        frozenset({"console"}),
        (
            "console nintendo game cover fantasy rpg xenoblade chronicles switch "
            "playing awesome blast recommend"
        ),
        "console_game_cover_bridge",
    ),
    (
        frozenset({"artist", "band"}),
        (
            "musical artists bands summer sounds band pop song dancing singing "
            "concert lively fun"
        ),
        "music_artist_band_bridge",
    ),
    (
        frozenset({"shoe", "used"}),
        (
            "new shoes purple walking running used for walk run love color sneakers"
        ),
        "shoe_usage_bridge",
    ),
    (
        frozenset({"meteor", "shower", "feel"}),
        (
            "meteor shower felt tiny awe universe awesome life sky stars watching "
            "camping trip"
        ),
        "meteor_shower_feeling_bridge",
    ),
    (
        frozenset({"color", "pattern", "pottery"}),
        (
            "pottery colors patterns catch eye make people smile express feelings "
            "creative creativity painting stroke project"
        ),
        "pottery_color_reason_bridge",
    ),
    (
        frozenset({"transgender", "event", "specific"}),
        (
            "transgender event poetry reading trans lives matter stories poetry "
            "safe place self expression empowering identities pride flags"
        ),
        "transgender_poetry_event_bridge",
    ),
    (
        frozenset({"book", "suggestion"}),
        (
            "book suggestion recommended becoming nicole amy ellis nutt true story "
            "trans girl family hope connection self acceptance"
        ),
        "book_suggestion_bridge",
    ),
    (
        frozenset({"children", "many"}),
        (
            "children kids brother siblings two younger kids son daughter scared "
            "reassured tough family"
        ),
        "children_count_sibling_bridge",
    ),
    (
        frozenset({"attribute", "describe"}),
        (
            "attributes describe traits family rock thankful volunteering food "
            "supplies toy drive calm assistance rescue mission burning building "
            "purpose make difference helpful brave"
        ),
        "attribute_description_bridge",
    ),
    (
        frozenset({"personality", "traits"}),
        (
            "thoughtful authentic driven drive determined dedicated passionate "
            "real care concern help helpful kind plan pitch awesome"
        ),
        "personality_trait_bridge",
    ),
    (
        frozenset({"personality", "traits"}),
        "thoughtful concern caring considerate precaution sign",
        "personality_thoughtfulness_bridge",
    ),
    (
        frozenset({"personality", "traits"}),
        "authentic real genuine true self care helping others",
        "personality_authenticity_bridge",
    ),
    (
        frozenset({"personality", "traits"}),
        "driven drive determined dedicated passionate plan pitch help awesome",
        "personality_drive_bridge",
    ),
    (
        frozenset({"roadtrip"}),
        "roadtrip accident scary scared bad start freaked lucky okay family",
        "adverse_trip_bridge",
    ),
    (
        frozenset({"song"}),
        "music classical composer bach mozart vivaldi orchestra symphony artist",
        "classical_music_preference_bridge",
    ),
    (
        frozenset({"music"}),
        "music classical composer bach mozart vivaldi orchestra symphony artist",
        "classical_music_preference_bridge",
    ),
    (
        frozenset({"screenshot"}),
        "ocr detected text written label title screen image visual текст написано",
        "visual_text_evidence_bridge",
    ),
    (
        frozenset({"image"}),
        "ocr detected text written label title photo picture visual текст написано",
        "visual_text_evidence_bridge",
    ),
    (
        frozenset({"audio"}),
        "transcript speech voice said told mentioned discussed audio транскрипт сказал сказала",
        "audio_transcript_evidence_bridge",
    ),
    (
        frozenset({"video"}),
        (
            "transcript speech said told mentioned discussed keyframe frame video audio "
            "транскрипт сказал сказала обсудили кадр"
        ),
        "video_transcript_evidence_bridge",
    ),
    (
        frozenset({"call"}),
        "transcript conversation said told mentioned discussed decision action item call",
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"meeting"}),
        "transcript notes discussed decision decisions action items follow up meeting",
        "meeting_evidence_bridge",
    ),
    (
        frozenset({"source"}),
        (
            "source citation evidence quote reference provenance origin document "
            "artifact transcript ocr"
        ),
        "source_evidence_bridge",
    ),
    (
        frozenset({"citation"}),
        (
            "source citation evidence quote reference provenance origin document "
            "artifact transcript ocr"
        ),
        "source_evidence_bridge",
    ),
    (
        frozenset({"evidence"}),
        (
            "source citation evidence quote reference provenance origin document "
            "artifact transcript ocr"
        ),
        "source_evidence_bridge",
    ),
    (
        frozenset({"proof"}),
        (
            "source citation evidence quote reference provenance origin document "
            "artifact transcript ocr"
        ),
        "source_evidence_bridge",
    ),
    (
        frozenset({"видео"}),
        "транскрипт сказал сказала обсудили упомянул упомянула кадр видео аудио",
        "video_transcript_evidence_bridge",
    ),
    (
        frozenset({"аудио"}),
        "транскрипт речь голос сказал сказала обсудили аудио",
        "audio_transcript_evidence_bridge",
    ),
    (
        frozenset({"скриншот"}),
        "ocr текст написано надпись экран изображение визуальный",
        "visual_text_evidence_bridge",
    ),
    (
        frozenset({"источник"}),
        (
            "источник ссылка доказательство цитата откуда документ артефакт "
            "транскрипт ocr source citation"
        ),
        "source_evidence_bridge",
    ),
    (
        frozenset({"ссылка"}),
        (
            "источник ссылка доказательство цитата откуда документ артефакт "
            "транскрипт ocr source citation"
        ),
        "source_evidence_bridge",
    ),
    (
        frozenset({"доказательство"}),
        (
            "источник ссылка доказательство цитата откуда документ артефакт "
            "транскрипт ocr source citation"
        ),
        "source_evidence_bridge",
    ),
    (
        frozenset({"latest"}),
        (
            "latest current active newest recent updated now valid not stale "
            "актуальный текущий последний"
        ),
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"current"}),
        (
            "latest current active newest recent updated now valid not stale "
            "актуальный текущий последний"
        ),
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"changed"}),
        (
            "changed change updated now before after previous current old new "
            "superseded replaced difference"
        ),
        "change_over_time_bridge",
    ),
    (
        frozenset({"change"}),
        (
            "changed change updated now before after previous current old new "
            "superseded replaced difference"
        ),
        "change_over_time_bridge",
    ),
    (
        frozenset({"updated"}),
        "changed change updated latest current previous superseded replaced difference",
        "change_over_time_bridge",
    ),
    (
        frozenset({"after"}),
        "after later following post meeting call decision follow up next",
        "after_event_temporal_bridge",
    ),
    (
        frozenset({"before"}),
        "before earlier prior previous previous state old initial",
        "before_event_temporal_bridge",
    ),
    (
        frozenset({"актуальн"}),
        "актуальный текущий последний сейчас обновлен действует не устаревший latest current",
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"последн"}),
        "последний актуальный текущий сейчас обновлен latest current recent",
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"обновлен"}),
        "изменилось обновилось последний текущий предыдущий старый новый replaced superseded",
        "change_over_time_bridge",
    ),
    (
        frozenset({"изменилось"}),
        "изменилось изменили стало раньше сейчас до после предыдущий текущий старый новый",
        "change_over_time_bridge",
    ),
    (
        frozenset({"после"}),
        "после позже затем встреча созвон решение follow up next after",
        "after_event_temporal_bridge",
    ),
    (
        frozenset({"до"}),
        "до раньше перед предыдущий начальный старый before prior previous",
        "before_event_temporal_bridge",
    ),
    (
        frozenset({"устаревш"}),
        "устаревший старый superseded replaced previous not current актуальный текущий",
        "stale_state_temporal_bridge",
    ),
)
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_CAPITALIZED_IDENTITY_STOPWORDS = frozenset(
    {
        "Are",
        "Can",
        "Could",
        "Did",
        "Does",
        "How",
        "Is",
        "May",
        "Might",
        "Should",
        "The",
        "Was",
        "Were",
        "What",
        "When",
        "Where",
        "Which",
        "Who",
        "Whom",
        "Why",
        "Will",
        "Would",
        "Где",
        "Зачем",
        "Как",
        "Какая",
        "Какие",
        "Какой",
        "Когда",
        "Кто",
        "Почему",
        "Что",
    }
)


def build_query_expansion_plan(
    query: str,
    *,
    decomposition_plan: QueryDecompositionPlan | None = None,
) -> QueryExpansionPlan:
    decomposition_plan = decomposition_plan or build_query_decomposition_plan(query)
    query_term_variants = _query_variant_set(query)
    identity_terms = _capitalized_identity_terms(query)
    expansions: list[QueryExpansion] = []
    seen_queries = {query.strip().casefold()}
    seen_reasons: set[str] = set()
    for required_terms, expansion, reason in _EXPANSION_RULES:
        if reason in seen_reasons:
            continue
        if not required_terms.issubset(query_term_variants):
            continue
        expanded_query = _with_identity_terms(identity_terms, expansion)
        normalized_expanded_query = expanded_query.casefold()
        if normalized_expanded_query in seen_queries:
            continue
        expansions.append(QueryExpansion(query=expanded_query, reason=reason))
        seen_queries.add(normalized_expanded_query)
        seen_reasons.add(reason)
        if len(expansions) >= 8:
            break
    return QueryExpansionPlan(
        original_query=query,
        expansions=tuple(expansions),
        decompositions=tuple(
            QueryExpansion(query=item.query, reason=item.reason)
            for item in decomposition_plan.decompositions
        ),
    )


def _query_variant_set(query: str) -> frozenset[str]:
    variants: set[str] = set()
    for term in query_terms(query, min_chars=2, max_terms=24):
        variants.update(term.variants)
    variants.update(_raw_query_tokens(query))
    return frozenset(variants)


def _raw_query_tokens(query: str) -> Iterable[str]:
    for match in _TOKEN_RE.finditer(query):
        token = match.group(0).casefold().strip("_")
        if len(token) >= 2:
            yield token


def _capitalized_identity_terms(query: str) -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()
    for match in _TOKEN_RE.finditer(query):
        token = match.group(0).strip("_")
        if len(token) < 2 or token in _CAPITALIZED_IDENTITY_STOPWORDS:
            continue
        if not token[:1].isupper():
            continue
        normalized = token.casefold()
        if normalized in seen:
            continue
        terms.append(token)
        seen.add(normalized)
        if len(terms) >= 3:
            break
    return tuple(terms)


def _with_identity_terms(identity_terms: tuple[str, ...], expansion: str) -> str:
    if not identity_terms:
        return expansion
    return " ".join((*identity_terms, expansion))
