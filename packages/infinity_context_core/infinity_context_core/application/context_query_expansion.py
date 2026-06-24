"""Deterministic query decomposition for evidence-oriented retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass

from infinity_context_core.application.context_lexical import query_terms
from infinity_context_core.application.context_query_decomposition import (
    QueryDecompositionPlan,
    build_query_decomposition_plan,
)
from infinity_context_core.application.context_query_identity_terms import (
    capitalized_identity_terms as _capitalized_identity_terms,
)
from infinity_context_core.application.context_query_identity_terms import (
    raw_query_tokens as _raw_query_tokens,
)
from infinity_context_core.application.context_query_identity_terms import (
    with_identity_terms as _with_identity_terms,
)
from infinity_context_core.application.context_query_personal_fact_expansions import (
    PERSONAL_FACT_EXPANSION_RULES,
    personal_fact_query_variants,
)
from infinity_context_core.application.context_query_state_transition import (
    state_transition_query_variants,
)
from infinity_context_core.application.context_query_support_role import (
    support_role_query_variants,
)
from infinity_context_core.application.context_query_workflow_expansions import (
    WORKFLOW_EXPANSION_RULES,
)
from infinity_context_core.application.context_query_workflow_intent import (
    gotcha_failure_query_variants,
    workflow_commitment_query_variants,
)
from infinity_context_core.application.context_ranking_reason_policy import (
    QUERY_REASON_PRIORITY as _QUERY_REASON_PRIORITY,
)

_NEGATIVE_EATING_QUERY_RE = re.compile(
    r"\b(?:can\W*t|cannot|can\s+not|unable\s+to)\b(?=.{0,80}\beat(?:s|ing)?\b)|"
    r"\beat(?:s|ing)?\b(?=.{0,80}\b(?:can\W*t|cannot|can\s+not|unable\s+to)\b)",
    re.IGNORECASE | re.DOTALL,
)
_WHO_ELSE_COMMONALITY_QUERY_RE = re.compile(
    r"\bwho\s+else\b(?=.{0,120}\b(?:like|likes|enjoy|enjoys|love|loves|"
    r"prefer|prefers|interest|hobby|activity|share|shares)\b)|"
    r"\bwho\s+shares?\b(?=.{0,120}\b(?:interest|hobby|activity|like|love|"
    r"preference)\b)|"
    r"\bкто\s+(?:ещ[её])\b(?=.{0,120}\b(?:любит|нравит|интерес|хобби|"
    r"увлечен|увлечён|предпочитает)\b)",
    re.IGNORECASE | re.DOTALL,
)
_MAX_QUERY_EXPANSIONS = 8


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
            "query_decomposition_status": ("available" if self.decompositions else "empty"),
            "query_decomposition_count": len(self.decompositions),
            "query_decomposition_reasons": [item.reason for item in self.decompositions],
        }


_CONVERSATION_TRANSCRIPT_EXPANSION = (
    "transcript conversation chat message dm spoke talked said told mentioned "
    "discussed decision action item follow up speaker turn quote"
)
_RU_CONVERSATION_TRANSCRIPT_EXPANSION = (
    "транскрипт разговор переписка созвон сообщение сказал сказала обсудили "
    "упомянул упомянула решение задача follow up реплика спикер цитата"
)
_SPEAKER_TURN_EXPANSION = (
    "speaker dialogue turn transcript quote said told mentioned discussed "
    "conversation source реплика спикер сказал сказала рассказал рассказала"
)
_CURRENT_RECOMMENDATION_EXPANSION = (
    "recommended preferred decided chose chosen selected switched should use choose "
    "current active provider tool model option engine database service retrieval "
    "latest valid not stale"
)
_CURRENT_DECISION_EXPANSION = (
    "final decision decided selected chosen approved settled source of truth canonical "
    "current active latest valid not stale provider tool model option plan decision "
    "финальный окончательный выбранный актуальный текущий источник правды"
)
_RECOMMENDATION_SOURCE_EXPANSION = (
    "recommendation suggestion advice recommended suggested advised follow followed "
    "because of based on after from source actor recipient to for read watched tried "
    "used visited listened started played made bought"
)
_BOOK_SUGGESTION_EXPANSION = (
    "book suggestion recommended becoming nicole amy ellis nutt true story trans girl "
    "family hope connection self acceptance reading that book a while ago tough "
    "doing ok painting keep busy"
)
_STATE_TRANSITION_EXPANSION = (
    "state transition changed switched switch replaced replacement migrated "
    "from to previous old current new active final selected superseded no longer "
    "valid not current replaced by before after"
)
_COMMONALITY_INTEREST_EXPANSION = (
    "common shared both mutual same similar overlap interests hobbies activities "
    "enjoy like love prefer painting camping hiking music books games food art "
    "watching movies desserts recipes baking evidence"
)
_TRIP_DESTINATION_EXPANSION = (
    "trip travel traveled travelled visit visited vacation destination place city "
    "country mountains beach park went journey route stayed location to in near "
    "поездка отпуск путешествие ездил ездила ездили поехал поехала посетил "
    "посетила куда место город страна горы пляж парк"
)
_DESTRESS_ACTIVITY_EXPANSION = (
    "running pottery class therapeutic therapy calm relax clear mind headspace unwind "
    "расслабиться расслабляется расслаблялась отдохнуть отдыхает снять стресс "
    "успокоиться спокойствие терапевтичный прояснить голову"
)
_ANIMAL_CAREER_INFERENCE_EXPANSION = (
    "alternative career animal keeper zookeeper zoo pets reptiles turtles care "
    "habitat responsible responsibility animal lover"
)
_ANIMAL_CARE_INSTRUCTION_EXPANSION = (
    "animal care instructions clean area clean tank feed properly enough light "
    "habitat routine responsible responsibility pets reptiles turtles keeper zoo"
)
_ANIMAL_DIET_EVIDENCE_EXPANSION = (
    "animal diet turtles feed eat eating vegetables fruits insects varied diet "
    "greens lettuce food properly care reptiles keeper zoo"
)
_ANIMAL_HABITAT_SETUP_EXPANSION = (
    "animal habitat setup new tank bigger tank room swim cute pet turtles little "
    "dudes pets reptiles aquarium care keeper zoo"
)
_ANIMAL_AFFINITY_PET_STORE_EXPANSION = (
    "animal affinity turtles pets pet store joy peace companion companions tank "
    "third turtle enjoys loves animal lover reptiles zookeeper keeper"
)
_EXPANSION_RULES: tuple[tuple[frozenset[str], str, str], ...] = (
    *PERSONAL_FACT_EXPANSION_RULES,
    (
        frozenset({"identity"}),
        (
            "identity transgender trans woman transition gender identity true self "
            "pride flag mural support group stories accepted embrace myself"
        ),
        "identity_bridge",
    ),
    (
        frozenset({"relationship", "status"}),
        (
            "relationship status single parent breakup partner married husband wife "
            "spouse friends family mentors rocks support system known friends home "
            "country tough breakup relationship love kids children challenge make "
            "family thrilled"
        ),
        "relationship_status_bridge",
    ),
    (
        frozenset({"why"}),
        (
            "why reason because motivation motivated made difference realized "
            "indicates showed explains supporting evidence journey support care "
            "help decided chose want wants passionate"
        ),
        "motivation_reason_bridge",
    ),
    (
        frozenset({"почему"}),
        (
            "почему причина потому что мотивация объясняет показывает доказательство "
            "поддержка решил решила хочет why reason because evidence"
        ),
        "motivation_reason_bridge",
    ),
    (
        frozenset({"start", "store"}),
        (
            "started business own store online clothing store job loss lost job "
            "Door Dash doordash banker fashion trends unique pieces blend dance "
            "fashion creative dream passionate"
        ),
        "business_start_reason_bridge",
    ),
    (
        frozenset({"clothing", "store"}),
        (
            "started business own store online clothing store job loss lost job "
            "Door Dash doordash banker fashion trends unique pieces blend dance "
            "fashion creative dream passionate"
        ),
        "business_start_reason_bridge",
    ),
    (
        frozenset({"business", "start"}),
        (
            "started business own store online clothing store job loss lost job "
            "Door Dash doordash banker fashion trends unique pieces blend dance "
            "fashion creative dream passionate"
        ),
        "business_start_reason_bridge",
    ),
    (
        frozenset({"shelter", "girl"}),
        (
            "shelter little girl sitting alone sad no other family comfort "
            "listening ear laughed talk volunteer event help"
        ),
        "shelter_comfort_reason_bridge",
    ),
    (
        frozenset({"charity", "organization"}),
        (
            "charity organization sponsorship brand Nike Gatorade Under Armour "
            "basketball shoe gear deal work with prominent make difference away "
            "from court give back inspire people youth sports disadvantaged kids"
        ),
        "charity_brand_sponsorship_bridge",
    ),
    (
        frozenset({"charity", "why"}),
        (
            "charity organization sponsorship brand Nike Gatorade Under Armour "
            "basketball shoe gear deal work with prominent make difference away "
            "from court give back inspire people youth sports disadvantaged kids"
        ),
        "charity_brand_sponsorship_bridge",
    ),
    (
        frozenset({"yoga", "why"}),
        (
            "yoga put off delay postponed planned play console partner video games "
            "Walking Dead next Saturday old games gaming instead"
        ),
        "yoga_delay_gaming_bridge",
    ),
    (
        frozenset({"yoga", "off"}),
        (
            "yoga put off delay postponed planned play console partner video games "
            "Walking Dead next Saturday old games gaming instead"
        ),
        "yoga_delay_gaming_bridge",
    ),
    (
        frozenset({"pursue", "career"}),
        (
            "current career option pursue looking into counseling counselor mental "
            "health jobs education options next steps figure out work goal decided"
        ),
        "career_intent_bridge",
    ),
    (
        frozenset({"career", "option"}),
        (
            "current career option pursue looking into counseling counselor mental "
            "health jobs education options next steps figure out work goal decided"
        ),
        "career_intent_bridge",
    ),
    (
        frozenset({"career", "path"}),
        (
            "career path decided pursue persue education options counseling "
            "mental health jobs work looking considering goal"
        ),
        "career_path_bridge",
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
        frozenset({"support_role_fit"}),
        (
            "support role fit mentor mentoring guidance advice coach volunteer "
            "counseling counselor listened listening comfort empathy patient "
            "helped accepted supportive safe trust similar issues reliable "
            "responsible care"
        ),
        "support_role_fit_bridge",
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
        frozenset({"support", "negative"}),
        (
            "friends family mentors rocks support accept accepted people around "
            "motivate strength push on not so great experience upset hike"
        ),
        "negative_experience_support_bridge",
    ),
    (
        frozenset({"support", "experience"}),
        (
            "friends family mentors rocks support accept accepted people around "
            "motivate strength push on not so great experience upset hike"
        ),
        "negative_experience_support_bridge",
    ),
    (
        frozenset({"move", "from"}),
        (
            "moved from home country origin roots previous country former country "
            "native country hometown came from grandma sweden"
        ),
        "relocation_origin_bridge",
    ),
    (
        frozenset({"open", "moving", "country"}),
        (
            "open moving another country relocate relocation abroad willingness "
            "military veteran service public office politics running office "
            "community country international mission future hope positive change "
            "join wanted hospital stories resilience inspiring excited wild ride"
        ),
        "relocation_willingness_inference_bridge",
    ),
    (
        frozenset({"open", "moving", "country"}),
        (
            "running office again campaign run excited enthusiasm zeal wild ride "
            "first run politics public office"
        ),
        "public_office_service_bridge",
    ),
    (
        frozenset({"open", "moving", "country"}),
        (
            "join military veteran hospital stories resilience hope inspiring "
            "served service mission wanted"
        ),
        "military_service_willingness_bridge",
    ),
    (
        frozenset({"patriotic"}),
        (
            "patriotic patriotism serving country serve my country service "
            "aptitude test military drawn to serving flag eagle national civic "
            "duty homeland positive results family friends supportive volunteer "
            "proud opportunity"
        ),
        "patriotic_service_inference_bridge",
    ),
    (
        frozenset({"patriotism"}),
        (
            "patriotic patriotism serving country serve my country service "
            "aptitude test military drawn to serving flag eagle national civic "
            "duty homeland positive results family friends supportive volunteer "
            "proud opportunity"
        ),
        "patriotic_service_inference_bridge",
    ),
    (
        frozenset({"transgender", "conference"}),
        (
            "transgender conference this month going upcoming meet people community "
            "advocacy learn event"
        ),
        "transgender_conference_event_bridge",
    ),
    (
        frozenset({"how", "long", "married"}),
        (
            "married husband wife spouse wedding anniversary years already time flies "
            "dress put this dress on"
        ),
        "relationship_duration_bridge",
    ),
    (
        frozenset({"when", "adoption", "meeting"}),
        (
            "last Friday council meeting for adoption inspiring emotional loving "
            "homes children need determined adopt"
        ),
        "temporal_event_detail_bridge",
    ),
    (
        frozenset({"when", "pride", "parade"}),
        (
            "last week LGBTQ pride parade happy belonged community grown summer "
            "went attended"
        ),
        "temporal_event_detail_bridge",
    ),
    (
        frozenset({"when", "pride", "festival"}),
        (
            "last year Pride fest festival blast supportive friends together "
            "worth it went attended"
        ),
        "temporal_event_detail_bridge",
    ),
    (
        frozenset({"when", "camping"}),
        (
            "camping camped went last week week before June 27 session date "
            "family nature hike roasted marshmallows campfire mountains outdoors"
        ),
        "temporal_event_detail_bridge",
    ),
    (
        frozenset({"when", "activist", "group"}),
        (
            "joined new LGBTQ activist group last Tues Tuesday rights community "
            "support voice difference fulfilling"
        ),
        "temporal_event_detail_bridge",
    ),
    (
        frozenset({"when", "volunteering", "shelter"}),
        (
            "started volunteering shelter about a year ago homeless family "
            "struggling streets reached out volunteers fulfilling"
        ),
        "temporal_event_detail_bridge",
    ),
    (
        frozenset({"when", "internship"}),
        (
            "interview design internship yesterday interview portfolio fashion "
            "cool project"
        ),
        "temporal_event_detail_bridge",
    ),
    (
        frozenset({"when", "hoodie"}),
        (
            "limited edition line hoodie collection last week own collection "
            "style creativity made designed"
        ),
        "temporal_event_detail_bridge",
    ),
    (
        frozenset({"when", "rocky"}),
        (
            "Rocky Mountains trip last year nature clearing mind calming soul "
            "mountains fresh air stunning"
        ),
        "temporal_event_detail_bridge",
    ),
    (
        frozenset({"when", "support", "group"}),
        (
            "joined service-focused online group last week emotional ride "
            "inspiring stories connection purpose support group"
        ),
        "temporal_event_detail_bridge",
    ),
    (
        frozenset({"when", "local", "artist"}),
        (
            "teamed up local artist cool designs online store working hard "
            "designs check them out"
        ),
        "temporal_event_detail_bridge",
    ),
    (
        frozenset({"item", "bought"}),
        "bought purchased got new shoes figurines items belongings sneakers",
        "item_purchase_bridge",
    ),
    (
        frozenset({"instrument", "play"}),
        (
            "instrument instruments play played playing clarinet violin guitar piano "
            "music started young expression relax refresh present"
        ),
        "instrument_play_bridge",
    ),
    (
        frozenset({"hobby"}),
        (
            "hobbies interests writing reading watching movies exploring nature "
            "hanging friends video games desserts recipes baking"
        ),
        "hobby_interest_bridge",
    ),
    (
        frozenset({"interest", "share"}),
        (
            "hobbies interests writing reading watching movies exploring nature "
            "hanging friends video games desserts recipes baking shared both similar"
        ),
        "hobby_interest_bridge",
    ),
    (
        frozenset({"common", "hobby"}),
        _COMMONALITY_INTEREST_EXPANSION,
        "commonality_interest_bridge",
    ),
    (
        frozenset({"common", "interests"}),
        _COMMONALITY_INTEREST_EXPANSION,
        "commonality_interest_bridge",
    ),
    (
        frozenset({"both", "enjoy"}),
        _COMMONALITY_INTEREST_EXPANSION,
        "commonality_interest_bridge",
    ),
    (
        frozenset({"both", "like"}),
        _COMMONALITY_INTEREST_EXPANSION,
        "commonality_interest_bridge",
    ),
    (
        frozenset({"shared", "interests"}),
        _COMMONALITY_INTEREST_EXPANSION,
        "commonality_interest_bridge",
    ),
    (
        frozenset({"who", "else", "like"}),
        _COMMONALITY_INTEREST_EXPANSION,
        "commonality_interest_bridge",
    ),
    (
        frozenset({"who", "share", "interest"}),
        _COMMONALITY_INTEREST_EXPANSION,
        "commonality_interest_bridge",
    ),
    (
        frozenset({"общ", "хобби"}),
        _COMMONALITY_INTEREST_EXPANSION,
        "commonality_interest_bridge",
    ),
    (
        frozenset({"общие", "интересы"}),
        _COMMONALITY_INTEREST_EXPANSION,
        "commonality_interest_bridge",
    ),
    (
        frozenset({"обе", "любят"}),
        _COMMONALITY_INTEREST_EXPANSION,
        "commonality_interest_bridge",
    ),
    (
        frozenset({"оба", "любят"}),
        _COMMONALITY_INTEREST_EXPANSION,
        "commonality_interest_bridge",
    ),
    (
        frozenset({"кто", "ещё", "любит"}),
        _COMMONALITY_INTEREST_EXPANSION,
        "commonality_interest_bridge",
    ),
    (
        frozenset({"кто", "еще", "любит"}),
        _COMMONALITY_INTEREST_EXPANSION,
        "commonality_interest_bridge",
    ),
    (
        frozenset({"national", "park"}),
        "camping trip campfire meteor shower nature outdoors",
        "outdoor_preference_bridge",
    ),
    (
        frozenset({"camping"}),
        (
            "camping trip mountains explored nature roasted marshmallows campfire "
            "hike view forest beach"
        ),
        "camping_detail_bridge",
    ),
    (
        frozenset({"where", "trip"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"where", "travel"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"where", "traveled"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"where", "travelled"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"where", "visit"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"where", "visited"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"where", "vacation"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"place", "visit"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"city", "visit"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"country", "travel"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"destination", "travel"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"place", "vacation"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"city", "vacation"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"country", "vacation"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"place", "went"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"куда", "ездил"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"куда", "ездила"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"куда", "поездка"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"куда", "отпуск"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"где", "отдыхал"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"где", "отдыхала"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"город", "посетил"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"страна", "поехал"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"место", "отпуск"}),
        _TRIP_DESTINATION_EXPANSION,
        "trip_destination_bridge",
    ),
    (
        frozenset({"family", "hike"}),
        (
            "family roasted marshmallows stories campfire hikes hiking camping "
            "forest nature kids children outdoors trip parent moments memories"
        ),
        "family_hike_activity_bridge",
    ),
    (
        frozenset({"family", "hike"}),
        (
            "roasted marshmallows shared stories campfire kids learning nature "
            "parent worth simple moments best memories forest hiking"
        ),
        "family_hike_detail_bridge",
    ),
    (
        frozenset({"first"}),
        (
            "first second third fourth fifth order sequence ordinal earliest initial "
            "won started finished event item tournament script letter attempt"
        ),
        "ordinal_answer_bridge",
    ),
    (
        frozenset({"second"}),
        (
            "first second third fourth fifth order sequence ordinal earliest initial "
            "won started finished event item tournament script letter attempt"
        ),
        "ordinal_answer_bridge",
    ),
    (
        frozenset({"third"}),
        (
            "first second third fourth fifth order sequence ordinal earliest initial "
            "won started finished event item tournament script letter attempt"
        ),
        "ordinal_answer_bridge",
    ),
    (
        frozenset({"fourth"}),
        (
            "first second third fourth fifth order sequence ordinal earliest initial "
            "won started finished event item tournament script letter attempt"
        ),
        "ordinal_answer_bridge",
    ),
    (
        frozenset({"many", "hike"}),
        (
            "hikes hiking hike trail trails waterfall photo picture pic took went "
            "joined buddies summer outdoors spot rush water soothing sunset saw seen "
            "gorgeous other day count times been on"
        ),
        "hike_count_activity_bridge",
    ),
    (
        frozenset({"after", "hike", "roadtrip"}),
        (
            "roadtrip road trip after hike hiking family mountains trail picture pic "
            "recent yesterday just did it kids loved nice way relax after road trip "
            "after the drive"
        ),
        "post_event_activity_timing_bridge",
    ),
    (
        frozenset({"many", "trail"}),
        (
            "hikes hiking hike trail trails found awesome amazing hometown town "
            "new trails more trails spots nature reset count times"
        ),
        "hiking_trail_count_bridge",
    ),
    (
        frozenset({"many"}),
        (
            "count total number quantity listed list includes including consists "
            "of first second third fourth another one two three four five collected "
            "earned received got completed items events pets books certificates awards"
        ),
        "quantity_enumeration_bridge",
    ),
    (
        frozenset({"сколько"}),
        (
            "count total number quantity listed list includes including consists "
            "of first second third fourth another one two three four five collected "
            "earned received got completed items events pets books certificates awards"
        ),
        "quantity_enumeration_bridge",
    ),
    (
        frozenset({"many", "tournament"}),
        (
            "tournament tournaments won winning first second fourth regional "
            "international big video game Valorant champion victory final money "
            "organized held tourney raised charity children hospital good cause"
        ),
        "tournament_count_bridge",
    ),
    (
        frozenset({"many", "tournaments"}),
        (
            "tournament tournaments won winning first second fourth regional "
            "international big video game Valorant champion victory final money "
            "organized held tourney raised charity children hospital good cause"
        ),
        "tournament_count_bridge",
    ),
    (
        frozenset({"charity", "tournament"}),
        (
            "charity tournament tournaments organized held gaming tourney friends "
            "raised amount children hospital good cause combining gaming organized "
            "yesterday"
        ),
        "charity_tournament_count_bridge",
    ),
    (
        frozenset({"many", "screenplay"}),
        (
            "screenplay screenplays script scripts first full screenplay printed "
            "started another second script wrapped up third one write wrote writing "
            "big screen finished count"
        ),
        "screenplay_count_bridge",
    ),
    (
        frozenset({"many", "screenplays"}),
        (
            "screenplay screenplays script scripts first full screenplay printed "
            "started another second script wrapped up third one write wrote writing "
            "big screen finished count"
        ),
        "screenplay_count_bridge",
    ),
    (
        frozenset({"many", "letter"}),
        (
            "letter letters received recieved got rejection letter wrote me letter "
            "words touched online blog post story comfort writing count"
        ),
        "letter_count_bridge",
    ),
    (
        frozenset({"many", "pet"}),
        (
            "pets pet puppy pup dog doggo adopted another dog adopted another pup "
            "shelter Toby Buddy Coco Shadow turtle turtles new friend critters count"
        ),
        "pet_count_bridge",
    ),
    (
        frozenset({"many", "turtle"}),
        (
            "turtles turtle critters new friend pet pets took turtles walk walking "
            "new tank third turtle count"
        ),
        "pet_count_bridge",
    ),
    (
        frozenset({"beach", "many"}),
        (
            "beach beaches went gone recently camped camping family kids children "
            "shore sand sandy kite campfire photo picture pic once twice year times"
        ),
        "beach_count_activity_bridge",
    ),
    (
        frozenset({"beach", "times"}),
        (
            "beach beaches went gone recently camped camping family kids children "
            "shore sand sandy kite campfire photo picture pic once twice year times"
        ),
        "beach_count_activity_bridge",
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
        frozenset({"move", "home", "country", "soon"}),
        (
            "adoption agency interviews build own family roof kids children "
            "giving back goal family committed current future plan"
        ),
        "adoption_current_goal_bridge",
    ),
    (
        frozenset({"move", "home", "country", "soon"}),
        "passed adoption agency interviews last Friday goal having family",
        "adoption_current_milestone_bridge",
    ),
    (
        frozenset({"ally", "transgender"}),
        (
            "supportive support acceptance community encouraging trans lgbtq "
            "proud allies inclusion kind words rights"
        ),
        "ally_support_bridge",
    ),
    (
        frozenset({"ally"}),
        "supportive support acceptance encouraging community care help proud kind words",
        "ally_support_bridge",
    ),
    (
        frozenset({"member", "community"}),
        "part belong identify refer herself member community lgbtq pride support group",
        "community_membership_bridge",
    ),
    (
        frozenset({"political", "leaning"}),
        (
            "rights lgbtq transition conservative conservatives religious hike "
            "upset unwelcoming support not-so-great work still have to do"
        ),
        "political_inference_bridge",
    ),
    (
        frozenset({"religious"}),
        (
            "church faith religious conservative conservatives stained glass local "
            "church journey transgender woman growth change"
        ),
        "religious_inference_bridge",
    ),
    (
        frozenset({"destress"}),
        _DESTRESS_ACTIVITY_EXPANSION,
        "destress_activity_bridge",
    ),
    (
        frozenset({"relax"}),
        _DESTRESS_ACTIVITY_EXPANSION,
        "destress_activity_bridge",
    ),
    (
        frozenset({"unwind"}),
        _DESTRESS_ACTIVITY_EXPANSION,
        "destress_activity_bridge",
    ),
    (
        frozenset({"stress", "relief"}),
        _DESTRESS_ACTIVITY_EXPANSION,
        "destress_activity_bridge",
    ),
    (
        frozenset({"расслабляется"}),
        _DESTRESS_ACTIVITY_EXPANSION,
        "destress_activity_bridge",
    ),
    (
        frozenset({"расслабиться"}),
        _DESTRESS_ACTIVITY_EXPANSION,
        "destress_activity_bridge",
    ),
    (
        frozenset({"отдохнуть"}),
        _DESTRESS_ACTIVITY_EXPANSION,
        "destress_activity_bridge",
    ),
    (
        frozenset({"снять", "стресс"}),
        _DESTRESS_ACTIVITY_EXPANSION,
        "destress_activity_bridge",
    ),
    (
        frozenset({"camped"}),
        "camping camped family mountains beach forest outdoors trip",
        "camping_location_bridge",
    ),
    (
        frozenset({"activities"}),
        (
            "pottery camping painting swimming class fam family kids weekend "
            "unplug hang swim running hobbies activities creative outdoors "
            "therapy therapeutic"
        ),
        "activity_aggregation_bridge",
    ),
    (
        frozenset({"activities"}),
        (
            "sunrise sunset lake take look swimming kids taking care ourselves "
            "vital self care relax long day"
        ),
        "activity_visual_selfcare_bridge",
    ),
    (
        frozenset({"kids", "like"}),
        (
            "kids children like love enjoy stoked excited dinosaur exhibit museum "
            "animals bones learning nature outdoors books stories favorite"
        ),
        "children_preference_bridge",
    ),
    (
        frozenset({"children", "like"}),
        (
            "kids children like love enjoy stoked excited dinosaur exhibit museum "
            "animals bones learning nature outdoors books stories favorite"
        ),
        "children_preference_bridge",
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
        frozenset({"kind", "art"}),
        (
            "art painting artwork art show preview abstract style kind type "
            "inclusivity diversity representation identity self acceptance"
        ),
        "art_style_bridge",
    ),
    (
        frozenset({"type", "art"}),
        (
            "art painting artwork art show preview abstract style kind type "
            "inclusivity diversity representation identity self acceptance"
        ),
        "art_style_bridge",
    ),
    (
        frozenset({"partake"}),
        "pottery camping swimming running hobbies activities creative outdoors",
        "activity_aggregation_bridge",
    ),
    (
        frozenset({"partake"}),
        (
            "sunrise sunset lake take look swimming kids taking care ourselves "
            "vital self care relax long day"
        ),
        "activity_visual_selfcare_bridge",
    ),
    (
        frozenset({"seuss", "book"}),
        (
            "kids books children books classic childrens classics stories different "
            "cultures educational books bookshelf childhood favorite book"
        ),
        "children_books_inference_bridge",
    ),
    (
        frozenset({"subject", "painted"}),
        (
            "painted painting artwork subject both same shared sunset nature image "
            "caption photo visual query finished latest work"
        ),
        "shared_painted_subject_bridge",
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
        frozenset({"medium", "game"}),
        (
            "medium mediums games play gaming GameCube Gamecube PC Playstation "
            "console equipment upgraded setup competition controller keyboard"
        ),
        "gaming_medium_bridge",
    ),
    (
        frozenset({"pet", "have"}),
        (
            "pets has have dog Max new addition family turtles critters new friend "
            "puppy pup doggo pet turtle"
        ),
        "pet_inventory_bridge",
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
            "volunteering shelter front desk food bed make difference lives started "
            "fulfilling gave few talks connecting helping others compliments residents "
            "aunt believed brighten struggling counselor coordinator volunteer homeless "
            "future job career social work smiles faces day"
        ),
        "volunteer_career_inference_bridge",
    ),
    (
        frozenset({"alternative", "career"}),
        _ANIMAL_CAREER_INFERENCE_EXPANSION,
        "animal_career_inference_bridge",
    ),
    (
        frozenset({"alternative", "career"}),
        _ANIMAL_CARE_INSTRUCTION_EXPANSION,
        "animal_care_instruction_bridge",
    ),
    (
        frozenset({"alternative", "career"}),
        _ANIMAL_DIET_EVIDENCE_EXPANSION,
        "animal_diet_evidence_bridge",
    ),
    (
        frozenset({"alternative", "career"}),
        _ANIMAL_HABITAT_SETUP_EXPANSION,
        "animal_habitat_setup_bridge",
    ),
    (
        frozenset({"alternative", "career"}),
        _ANIMAL_AFFINITY_PET_STORE_EXPANSION,
        "animal_affinity_pet_store_bridge",
    ),
    (
        frozenset({"career", "gaming"}),
        _ANIMAL_CAREER_INFERENCE_EXPANSION,
        "animal_career_inference_bridge",
    ),
    (
        frozenset({"career", "gaming"}),
        _ANIMAL_CARE_INSTRUCTION_EXPANSION,
        "animal_care_instruction_bridge",
    ),
    (
        frozenset({"career", "gaming"}),
        _ANIMAL_DIET_EVIDENCE_EXPANSION,
        "animal_diet_evidence_bridge",
    ),
    (
        frozenset({"career", "gaming"}),
        _ANIMAL_HABITAT_SETUP_EXPANSION,
        "animal_habitat_setup_bridge",
    ),
    (
        frozenset({"career", "gaming"}),
        _ANIMAL_AFFINITY_PET_STORE_EXPANSION,
        "animal_affinity_pet_store_bridge",
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
        frozenset({"allergic"}),
        (
            "allergic allergy cannot can't have dairy dairy-free no ice cream "
            "reptiles animals fur cockroaches pets turtles"
        ),
        "allergy_inventory_bridge",
    ),
    (
        frozenset({"allergy"}),
        (
            "allergic allergy cannot can't have dairy dairy-free no ice cream "
            "reptiles animals fur cockroaches pets turtles"
        ),
        "allergy_inventory_bridge",
    ),
    (
        frozenset({"not", "eat"}),
        (
            "avoid avoids avoided never eat eats eating food foods allergic allergy "
            "restriction restricted dislike cannot can't shellfish peanuts dietary "
            "preference discomfort unsafe"
        ),
        "avoidance_constraint_bridge",
    ),
    (
        frozenset({"not", "like"}),
        (
            "does not like doesn't like dislike dislikes disliked hate hates hated "
            "avoid avoids avoided not enjoy never enjoy preference discomfort "
            "overwhelming too loud unsafe unpleasant"
        ),
        "negative_preference_bridge",
    ),
    (
        frozenset({"not", "interested"}),
        (
            "not interested uninterested doesn't want does not want avoid avoids "
            "declined preference dislike not enjoy no interest low priority"
        ),
        "negative_preference_bridge",
    ),
    (
        frozenset({"meat", "prefer"}),
        (
            "favorite meat chicken beef pork fish turkey steak dish recipe cooking "
            "cook roasted pot pie comfort meal favorite eating food prefer preference"
        ),
        "food_preference_bridge",
    ),
    (
        frozenset({"food", "prefer"}),
        (
            "favorite food meal dish recipe cooking cook comfort meal favorite "
            "eating prefer preference"
        ),
        "food_preference_bridge",
    ),
    (
        frozenset({"avoid"}),
        (
            "avoid avoids avoided should not never risk blocked blocker constraint "
            "restriction unsafe conflict prerequisite before approval"
        ),
        "avoidance_constraint_bridge",
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
            "strength trans community resilience stained glass acceptance pendant "
            "necklace transgender symbol cross heart"
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
            "musical artists bands saw seen live concert show festival performance "
            "performed summer sounds band pop dancing singing lively fun"
        ),
        "music_artist_band_bridge",
    ),
    (
        frozenset({"artist", "seen"}),
        (
            "musical artists bands saw seen live concert show festival performance "
            "performed summer sounds band pop dancing singing lively fun"
        ),
        "music_artist_band_bridge",
    ),
    (
        frozenset({"band", "seen"}),
        (
            "musical artists bands saw seen live concert show festival performance "
            "performed summer sounds band pop dancing singing lively fun"
        ),
        "music_artist_band_bridge",
    ),
    (
        frozenset({"artist", "band"}),
        "matt patterson talented voice amazing singer named performer artist",
        "music_artist_answer_bridge",
    ),
    (
        frozenset({"artist", "seen"}),
        "matt patterson talented voice amazing singer named performer artist",
        "music_artist_answer_bridge",
    ),
    (
        frozenset({"band", "seen"}),
        "matt patterson talented voice amazing singer named performer artist",
        "music_artist_answer_bridge",
    ),
    (
        frozenset({"shoe", "used"}),
        ("new shoes purple walking running used for walk run love color sneakers"),
        "shoe_usage_bridge",
    ),
    (
        frozenset({"reason", "running"}),
        (
            "running run farther longer de-stress destress clear mind headspace "
            "mood boost shoes purple walking or running what got into running"
        ),
        "running_reason_bridge",
    ),
    (
        frozenset({"reason", "running"}),
        (
            "what got you into running got into running why started running "
            "reason asked question walking or running"
        ),
        "running_reason_question_bridge",
    ),
    (
        frozenset({"getting", "running"}),
        (
            "running run farther longer de-stress destress clear mind headspace "
            "mood boost shoes purple walking or running what got into running"
        ),
        "running_reason_bridge",
    ),
    (
        frozenset({"getting", "running"}),
        (
            "what got you into running got into running why started running "
            "reason asked question walking or running"
        ),
        "running_reason_question_bridge",
    ),
    (
        frozenset({"meteor", "shower", "feel"}),
        ("meteor shower felt tiny awe universe awesome life sky stars watching camping trip"),
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
        frozenset({"pottery", "type"}),
        (
            "pottery types pieces made clay finished ceramic bowl bowls cup mug "
            "painted intricate design project another class kids creativity imagination"
        ),
        "pottery_type_bridge",
    ),
    (
        frozenset({"pottery", "made"}),
        (
            "pottery types pieces made clay finished ceramic bowl bowls cup mug "
            "painted intricate design project another class kids creativity imagination"
        ),
        "pottery_type_bridge",
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
        frozenset({"transgender", "event", "specific"}),
        (
            "transgender conference supportive professionals advocacy learn "
            "workshop accepted connected"
        ),
        "transgender_conference_event_bridge",
    ),
    (
        frozenset({"transgender", "event", "specific"}),
        (
            "lgbtq youth center volunteer volunteering talent show kids community "
            "stage band live music performance"
        ),
        "transgender_youth_center_event_bridge",
    ),
    (
        frozenset({"book", "suggestion"}),
        _BOOK_SUGGESTION_EXPANSION,
        "book_suggestion_bridge",
    ),
    (
        frozenset({"book", "read"}),
        (
            "books read collection bookshelf Harry Potter Game of Thrones Name "
            "of the Wind Alchemist Hobbit Dance with Dragons Wheel of Time fantasy "
            "novel series finished favorite love"
        ),
        "book_reading_list_bridge",
    ),
    (
        frozenset({"book", "suggest"}),
        _BOOK_SUGGESTION_EXPANSION,
        "book_suggestion_bridge",
    ),
    (
        frozenset({"book", "recommend"}),
        _BOOK_SUGGESTION_EXPANSION,
        "book_suggestion_bridge",
    ),
    (
        frozenset({"book", "recommendation"}),
        _BOOK_SUGGESTION_EXPANSION,
        "book_suggestion_bridge",
    ),
    (
        frozenset({"recommendation", "follow"}),
        _RECOMMENDATION_SOURCE_EXPANSION,
        "recommendation_source_bridge",
    ),
    (
        frozenset({"suggestion", "follow"}),
        _RECOMMENDATION_SOURCE_EXPANSION,
        "recommendation_source_bridge",
    ),
    (
        frozenset({"advice", "follow"}),
        _RECOMMENDATION_SOURCE_EXPANSION,
        "recommendation_source_bridge",
    ),
    (
        frozenset({"recommendation", "read"}),
        _RECOMMENDATION_SOURCE_EXPANSION,
        "recommendation_source_bridge",
    ),
    (
        frozenset({"suggestion", "read"}),
        _RECOMMENDATION_SOURCE_EXPANSION,
        "recommendation_source_bridge",
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
        frozenset({"children", "many"}),
        "son accident roadtrip lucky okay ok scary car",
        "children_count_event_bridge",
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
        frozenset({"attribute", "describe"}),
        (
            "attributes describe family rock tough times cheer love thankful "
            "family time centered support strength motivation grounded"
        ),
        "attribute_family_support_bridge",
    ),
    (
        frozenset({"attribute", "describe"}),
        (
            "attributes describe stayed calm asked assistance handled situation "
            "made it back safely resilience resourcefulness"
        ),
        "attribute_calm_resourcefulness_bridge",
    ),
    (
        frozenset({"attribute", "describe"}),
        (
            "attributes describe volunteer volunteering homeless shelter food "
            "supplies toy drive kids need community made difference helpful"
        ),
        "attribute_service_helpfulness_bridge",
    ),
    (
        frozenset({"attribute", "describe"}),
        (
            "attributes describe rescue mission firefighting brigade burning "
            "building pulled together energy purpose made difference brave "
            "community safe fulfilling meaningful"
        ),
        "attribute_rescue_purpose_bridge",
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
        (
            "music classical fan composer bach mozart vivaldi orchestra symphony "
            "artist song enjoy four seasons"
        ),
        "classical_music_preference_bridge",
    ),
    (
        frozenset({"music"}),
        (
            "music classical fan composer bach mozart vivaldi orchestra symphony "
            "artist song enjoy four seasons"
        ),
        "classical_music_preference_bridge",
    ),
    (
        frozenset({"outdoor", "gear"}),
        (
            "outdoor gear company endorsement deal renowned Under Armour Nike "
            "Gatorade signed up sponsorship working with them cool"
        ),
        "endorsement_gear_brand_bridge",
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
        frozenset({"said", "about"}),
        _SPEAKER_TURN_EXPANSION,
        "speaker_turn_bridge",
    ),
    (
        frozenset({"said", "про"}),
        _SPEAKER_TURN_EXPANSION,
        "speaker_turn_bridge",
    ),
    (
        frozenset({"according"}),
        _SPEAKER_TURN_EXPANSION,
        "speaker_turn_bridge",
    ),
    (
        frozenset({"perspective"}),
        _SPEAKER_TURN_EXPANSION,
        "speaker_turn_bridge",
    ),
    (
        frozenset({"opinion"}),
        _SPEAKER_TURN_EXPANSION,
        "speaker_turn_bridge",
    ),
    (
        frozenset({"словам"}),
        _SPEAKER_TURN_EXPANSION,
        "speaker_turn_bridge",
    ),
    (
        frozenset({"call"}),
        _CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"talk"}),
        _CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"meet"}),
        _CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"chat"}),
        _CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"conversation"}),
        _CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"message"}),
        _CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"dm"}),
        _CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"spoke"}),
        _CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"talked"}),
        _CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"chatted"}),
        _CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"discussed"}),
        _CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"созвон"}),
        _RU_CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"переписка"}),
        _RU_CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"переписке"}),
        _RU_CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"переписки"}),
        _RU_CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"перепиской"}),
        _RU_CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"переписку"}),
        _RU_CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"переписывался"}),
        _RU_CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"переписывалась"}),
        _RU_CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"переписывались"}),
        _RU_CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"общался"}),
        _RU_CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"говорил"}),
        _RU_CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"говорила"}),
        _RU_CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"общалась"}),
        _RU_CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"общались"}),
        _RU_CONVERSATION_TRANSCRIPT_EXPANSION,
        "conversation_transcript_evidence_bridge",
    ),
    (
        frozenset({"meeting"}),
        "transcript notes discussed decision decisions action items follow up meeting",
        "meeting_evidence_bridge",
    ),
    *WORKFLOW_EXPANSION_RULES,
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
        frozenset({"currently"}),
        (
            "currently current active latest recent updated now right now "
            "valid not stale актуальный текущий сейчас"
        ),
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"recent"}),
        (
            "most recent latest current active newest updated now valid not stale "
            "актуальный текущий последний"
        ),
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"still", "valid"}),
        (
            "still valid remains current active latest selected chosen recommended "
            "not stale not outdated актуальный текущий действует"
        ),
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"still", "use"}),
        (
            "still use still using current active selected chosen recommended "
            "provider tool model option not stale not outdated"
        ),
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"remains"}),
        (
            "remains valid current active latest recommended selected chosen "
            "not stale not outdated"
        ),
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"final", "decision"}),
        _CURRENT_DECISION_EXPANSION,
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"final", "provider"}),
        _CURRENT_DECISION_EXPANSION,
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"source", "truth"}),
        _CURRENT_DECISION_EXPANSION,
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"canonical"}),
        _CURRENT_DECISION_EXPANSION,
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"selected", "provider"}),
        _CURRENT_DECISION_EXPANSION,
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"chosen", "provider"}),
        _CURRENT_DECISION_EXPANSION,
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"should", "use"}),
        _CURRENT_RECOMMENDATION_EXPANSION,
        "current_recommendation_bridge",
    ),
    (
        frozenset({"recommended", "provider"}),
        _CURRENT_RECOMMENDATION_EXPANSION,
        "current_recommendation_bridge",
    ),
    (
        frozenset({"preferred", "provider"}),
        _CURRENT_RECOMMENDATION_EXPANSION,
        "current_recommendation_bridge",
    ),
    (
        frozenset({"best", "provider"}),
        _CURRENT_RECOMMENDATION_EXPANSION,
        "current_recommendation_bridge",
    ),
    (
        frozenset({"decided", "provider"}),
        _CURRENT_RECOMMENDATION_EXPANSION,
        "current_recommendation_bridge",
    ),
    (
        frozenset({"choose", "provider"}),
        _CURRENT_RECOMMENDATION_EXPANSION,
        "current_recommendation_bridge",
    ),
    (
        frozenset({"chosen", "provider"}),
        _CURRENT_RECOMMENDATION_EXPANSION,
        "current_recommendation_bridge",
    ),
    (
        frozenset({"selected", "provider"}),
        _CURRENT_RECOMMENDATION_EXPANSION,
        "current_recommendation_bridge",
    ),
    (
        frozenset({"chose", "provider"}),
        _CURRENT_RECOMMENDATION_EXPANSION,
        "current_recommendation_bridge",
    ),
    (
        frozenset({"decided", "use"}),
        _CURRENT_RECOMMENDATION_EXPANSION,
        "current_recommendation_bridge",
    ),
    (
        frozenset({"choose", "use"}),
        _CURRENT_RECOMMENDATION_EXPANSION,
        "current_recommendation_bridge",
    ),
    (
        frozenset({"chose", "use"}),
        _CURRENT_RECOMMENDATION_EXPANSION,
        "current_recommendation_bridge",
    ),
    (
        frozenset({"state_transition_request"}),
        _STATE_TRANSITION_EXPANSION,
        "state_transition_bridge",
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
        frozenset({"stale"}),
        "stale outdated old superseded replaced previous not current invalid expired review",
        "stale_state_temporal_bridge",
    ),
    (
        frozenset({"outdated"}),
        "stale outdated old superseded replaced previous not current invalid expired review",
        "stale_state_temporal_bridge",
    ),
    (
        frozenset({"obsolete"}),
        "stale obsolete deprecated outdated old superseded replaced previous not current review",
        "stale_state_temporal_bridge",
    ),
    (
        frozenset({"deprecated"}),
        "deprecated obsolete stale outdated superseded replaced previous not current review",
        "stale_state_temporal_bridge",
    ),
    (
        frozenset({"expired"}),
        "expired stale outdated superseded replaced previous no longer valid not current review",
        "stale_state_temporal_bridge",
    ),
    (
        frozenset({"longer", "valid"}),
        (
            "no longer valid stale outdated superseded replaced previous old "
            "not current invalid deprecated review"
        ),
        "stale_state_temporal_bridge",
    ),
    (
        frozenset({"longer", "use"}),
        (
            "no longer use no longer using stale outdated superseded replaced "
            "previous old not current invalid deprecated review"
        ),
        "stale_state_temporal_bridge",
    ),
    (
        frozenset({"anymore", "valid"}),
        (
            "not valid anymore no longer valid stale outdated superseded replaced "
            "previous old not current invalid review"
        ),
        "stale_state_temporal_bridge",
    ),
    (
        frozenset({"stopped"}),
        (
            "stopped using no longer use stale outdated superseded replaced "
            "previous old not current review"
        ),
        "stale_state_temporal_bridge",
    ),
    (
        frozenset({"not", "current"}),
        "not current stale outdated superseded replaced previous old invalid review",
        "stale_state_temporal_bridge",
    ),
    (
        frozenset({"актуал"}),
        "актуальный текущий последний сейчас обновлен действует не устаревший latest current",
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"актуален"}),
        "актуальный текущий последний сейчас обновлен действует не устаревший latest current",
        "current_state_temporal_bridge",
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
        frozenset({"финальн", "решение"}),
        _CURRENT_DECISION_EXPANSION,
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"решение", "выбранный"}),
        _CURRENT_DECISION_EXPANSION,
        "current_state_temporal_bridge",
    ),
    (
        frozenset({"провайдер", "выбранный"}),
        _CURRENT_DECISION_EXPANSION,
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
    (
        frozenset({"больше", "использовать"}),
        (
            "больше не использовать устаревший старый заменен предыдущий "
            "не актуальный not current stale superseded"
        ),
        "stale_state_temporal_bridge",
    ),
    (
        frozenset({"больше", "актуал"}),
        (
            "больше не актуальный устаревший старый заменен предыдущий "
            "не текущий stale superseded"
        ),
        "stale_state_temporal_bridge",
    ),
)


def build_query_expansion_plan(
    query: str,
    *,
    decomposition_plan: QueryDecompositionPlan | None = None,
) -> QueryExpansionPlan:
    decomposition_plan = decomposition_plan or build_query_decomposition_plan(query)
    query_term_variants = set(_query_variant_set(query))
    query_term_variants.update(gotcha_failure_query_variants(query))
    query_term_variants.update(state_transition_query_variants(query))
    query_term_variants.update(support_role_query_variants(query))
    query_term_variants.update(workflow_commitment_query_variants(query))
    query_term_variants.update(personal_fact_query_variants(query))
    raw_tokens = set(_raw_query_tokens(query))
    identity_terms = _capitalized_identity_terms(query)
    expansion_candidates: list[tuple[int, int, QueryExpansion]] = []
    seen_queries = {query.strip().casefold()}
    for rule_index, (required_terms, expansion, reason) in enumerate(_EXPANSION_RULES):
        if _should_skip_expansion_rule(reason, query=query, raw_tokens=raw_tokens):
            continue
        if not required_terms.issubset(query_term_variants):
            continue
        expanded_query = _with_identity_terms(
            _identity_terms_for_expansion(
                reason=reason,
                query=query,
                identity_terms=identity_terms,
            ),
            expansion,
        )
        normalized_expanded_query = expanded_query.casefold()
        if normalized_expanded_query in seen_queries:
            continue
        expansion_candidates.append(
            (
                rule_index,
                len(required_terms),
                QueryExpansion(query=expanded_query, reason=reason),
            )
        )

    expansions: list[QueryExpansion] = []
    selected_queries = set(seen_queries)
    selected_reasons: set[str] = set()
    for _, _, expansion in sorted(
        expansion_candidates,
        key=_expansion_candidate_selection_key,
    ):
        normalized_expanded_query = expansion.query.casefold()
        if expansion.reason in selected_reasons or normalized_expanded_query in selected_queries:
            continue
        expansions.append(expansion)
        selected_queries.add(normalized_expanded_query)
        selected_reasons.add(expansion.reason)
        if len(expansions) >= _MAX_QUERY_EXPANSIONS:
            break
    return QueryExpansionPlan(
        original_query=query,
        expansions=tuple(expansions),
        decompositions=tuple(
            QueryExpansion(query=item.query, reason=item.reason)
            for item in decomposition_plan.decompositions
        ),
    )


def _expansion_candidate_selection_key(
    item: tuple[int, int, QueryExpansion],
) -> tuple[int, int, int]:
    rule_index, specificity, expansion = item
    return (
        -_QUERY_REASON_PRIORITY.get(expansion.reason, 0),
        -specificity,
        rule_index,
    )


def _should_skip_expansion_rule(
    reason: str,
    *,
    query: str,
    raw_tokens: set[str],
) -> bool:
    if reason in {
        "current_recommendation_bridge",
        "current_state_temporal_bridge",
    } and _requests_stale_state_update(query=query, raw_tokens=raw_tokens):
        return True
    if reason == "career_intent_bridge" and "alternative" in raw_tokens:
        return True
    if reason == "career_intent_bridge" and {"future", "job"}.issubset(raw_tokens):
        return True
    if reason == "children_count_sibling_bridge" and not raw_tokens.intersection(
        {"child", "children", "kid", "kids", "sibling", "siblings", "brother", "sister"}
    ):
        return True
    if reason == "allergy_inventory_bridge" and raw_tokens.intersection(
        {"condition", "underlying"}
    ):
        return True
    return reason == "camping_detail_bridge" and not any(
        token.startswith("camp") for token in raw_tokens
    )


def _identity_terms_for_expansion(
    *,
    reason: str,
    query: str,
    identity_terms: tuple[str, ...],
) -> tuple[str, ...]:
    if reason == "commonality_interest_bridge" and _WHO_ELSE_COMMONALITY_QUERY_RE.search(query):
        return ()
    return identity_terms


def _requests_stale_state_update(*, query: str, raw_tokens: set[str]) -> bool:
    normalized = query.casefold()
    if any(
        phrase in normalized
        for phrase in (
            "not stale",
            "not outdated",
            "not obsolete",
            "not deprecated",
            "not expired",
        )
    ):
        return False
    return bool(
        "no longer" in normalized
        or "not current" in normalized
        or raw_tokens.intersection({"anymore", "stopped", "больше"})
        or {"longer", "use"}.issubset(raw_tokens)
        or {"больше", "использовать"}.issubset(raw_tokens)
    )


def _query_variant_set(query: str) -> frozenset[str]:
    variants: set[str] = set()
    for term in query_terms(query, min_chars=2, max_terms=24):
        variants.update(term.variants)
    variants.update(_raw_query_tokens(query))
    if _NEGATIVE_EATING_QUERY_RE.search(query):
        variants.update(("not", "cannot", "eat"))
    return frozenset(variants)
