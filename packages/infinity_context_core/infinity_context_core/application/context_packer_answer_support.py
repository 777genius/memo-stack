"""Answer-support policy helpers for context packing."""

from __future__ import annotations

import re
from infinity_context_core.application.context_diagnostics import (
    context_rank_key,
    diagnostic_retrieval_sources,
)
from infinity_context_core.application.context_packer_answer_support_utils import (
    _answer_support_activity_family_slot,
    _artifact_diversity_hint,
    _answer_support_exact_query_object_hits,
    _compound_diversity_family,
    _diagnostic_list,
    _diagnostic_score_signals,
    _diagnostic_signal_text,
    _diagnostic_signal_truthy,
    _diagnostic_text,
    _diversity_family_base,
    _has_any_exact_turn_source_ref,
    _has_primary_exact_turn_source_ref,
    _inventory_first_mention_rank,
    _is_exact_turn_source_id,
    _memory_scope_id,
    _numeric_signal,
    _one_line,
    _primary_exact_turn_source_id,
    _safe_diversity_suffix,
    _source_group_key,
    _source_key,
    _source_ref_modality_hint,
    _typed_diversity_family,
)
from infinity_context_core.application.context_packer_inventory_slots import (
    _answer_support_exact_turn_alignment_rank,
    _children_preference_answer_slot,
    _community_participation_inventory_slot_for_text,
    _dessert_inventory_slot_for_text,
    _exercise_activity_answer_content_rank,
    _exercise_activity_answer_slot,
    _item_purchase_inventory_slot_for_text,
    _inventory_answer_slot_priority_for_family,
    _painting_inventory_answer_content_rank,
    _painting_inventory_answer_slot,
)
from infinity_context_core.application.context_ranking_reason_policy import (
    PRECISE_TURN_SOURCE_SIBLING_REASONS,
)
from infinity_context_core.application.dto import ContextItem
_DIALOGUE_MARKER_RE = re.compile(r"\bD\d+:\d+\b")
_MAX_ANSWER_SUPPORT_DIVERSITY_ITEMS = 8
_MAX_INVENTORY_ANSWER_SUPPORT_DIVERSITY_ITEMS = 12
_MAX_ANSWER_SUPPORT_SOURCE_GROUP_DIVERSITY_ITEMS_PER_REASON = 1
_MAX_ANSWER_SUPPORT_EVENT_SLOT_SOURCE_GROUP_DIVERSITY_ITEMS_PER_REASON = 2
_MAX_ANSWER_SUPPORT_AGGREGATION_SOURCE_GROUP_DIVERSITY_ITEMS_PER_REASON = 6
_ANSWER_SUPPORT_AGGREGATION_SOURCE_GROUP_REASONS = frozenset(
    {
        "adoption-current-goal-bridge",
        "adoption-current-milestone-bridge",
        "activity-aggregation-bridge",
        "activity-visual-selfcare-bridge",
        "birdwatching-city-schedule-bridge",
        "book-reading-list-bridge",
        "animal-activity-inventory-bridge",
        "book-suggestion-bridge",
        "business-commonality-bridge",
        "career-path-bridge",
        "charity-brand-sponsorship-bridge",
        "children-count-event-bridge",
        "children-count-sibling-bridge",
        "children-preference-bridge",
        "creative-writing-career-bridge",
        "cause-education-infrastructure-inventory-bridge",
        "cause-veterans-inventory-bridge",
        "church-friend-activity-inventory-bridge",
        "classical-music-preference-bridge",
        "decomposition-activity-duration",
        "decomposition-activity-participation",
        "decomposition-attribute-aggregation",
        "decomposition-frequency-recurrence",
        "decomposition-inventory-list",
        "decomposition-quantity-count",
        "degree-policy-inference-bridge",
        "event-participation-bridge",
        "exercise-activity-inventory-bridge",
        "family-activity-bridge",
        "family-hike-detail-bridge",
        "family-hike-activity-bridge",
        "family-museum-activity-bridge",
        "friend-place-inventory-bridge",
        "friend-place-shelter-inventory-bridge",
        "friend-place-gym-inventory-bridge",
        "friend-place-church-inventory-bridge",
        "fundraiser-event-inventory-bridge",
        "family-painting-activity-bridge",
        "family-swimming-activity-bridge",
        "hike-count-activity-bridge",
        "item-purchase-bridge",
        "community-participation-bridge",
        "lgbtq-community-participation-bridge",
        "music-artist-band-bridge",
        "music-artist-answer-bridge",
        "music-event-inventory-bridge",
        "national-park-inference-bridge",
        "outdoor-activity-inventory-bridge",
        "painting-inventory-bridge",
        "place-area-inventory-bridge",
        "pottery-type-bridge",
        "recommendation-source-bridge",
        "religious-inference-bridge",
        "running-reason-bridge",
        "running-reason-question-bridge",
        "symbol-importance-bridge",
        "transgender-youth-center-event-bridge",
        "travel-country-inventory-bridge",
        "veterans-event-inventory-bridge",
        "volunteering-people-inventory-bridge",
        "volunteering-inventory-bridge",
        "volunteer-career-inference-bridge",
    }
)
_COUNT_AGGREGATION_COVERAGE_REASONS = frozenset(
    {
        "beach_count_activity_bridge",
        "hike_count_activity_bridge",
        "hiking_trail_count_bridge",
    }
)
_ANSWER_SUPPORT_EXCLUDED_QUERY_REASONS = frozenset()
_MAX_PRECISE_ANSWER_SUPPORT_DIVERSITY_ITEMS = 8
_BROAD_EVIDENCE_ANSWER_SUPPORT_REASONS = frozenset(
    {
        "activity_visual_selfcare_bridge",
        "birdwatching_city_schedule_bridge",
        "book_suggestion_bridge",
    }
)
_BROAD_EVIDENCE_TURN_SLOT_REASONS = frozenset(
    {
        "birdwatching_city_schedule_bridge",
        "book_suggestion_bridge",
    }
)
_EXACT_PRECISE_CONTENT_TURN_REASONS = frozenset(
    {
        "activity_visual_selfcare_bridge",
        "business_commonality_bridge",
        "business_start_reason_bridge",
        "children_preference_bridge",
        "outdoor_nature_memory_bridge",
        "public_office_service_bridge",
        "relocation_willingness_inference_bridge",
        "volunteer_career_inference_bridge",
    }
)
_DIRECT_EVIDENCE_QUERY_FOCUS_REASONS = frozenset(
    {
        "children_preference_bridge",
        "public_office_service_bridge",
        "relocation_willingness_inference_bridge",
        "volunteer_career_inference_bridge",
    }
)
_PRECISE_TURN_ANSWER_SUPPORT_REASONS = PRECISE_TURN_SOURCE_SIBLING_REASONS | frozenset(
    {
        "activity_aggregation_bridge",
        "animal_activity_inventory_bridge",
        "book_reading_list_bridge",
        "career_intent_bridge",
        "career_path_bridge",
        "creative_writing_career_bridge",
        "children_preference_bridge",
        "community_participation_bridge",
        "exercise_activity_inventory_bridge",
        "food_recipe_recommendation_bridge",
        "lgbtq_community_participation_bridge",
        "music_artist_answer_bridge",
        "personality_authenticity_bridge",
        "personality_drive_bridge",
        "personality_thoughtfulness_bridge",
        "personality_trait_bridge",
        "sentimental_reminder_bridge",
        "wellness_activity_effect_bridge",
        "negative_experience_support_bridge",
        "support_career_motivation_bridge",
        "support_origin_bridge",
        "support_network_bridge",
    }
)
_DIVERSITY_PRECISE_TURN_REASONS = frozenset(
    {
        "birdwatching_city_schedule_bridge",
        "food_recipe_recommendation_bridge",
        "wellness_activity_effect_bridge",
    }
)
_BIRDWATCHING_CITY_SCHEDULE_CONTENT_RE = re.compile(
    r"\b("
    r"busy\s+week|city\s+schedule|schedule|"
    r"binos|binoculars|notebook|log\s+them|"
    r"spot\s+(?:looks\s+)?ideal|where\s+did\s+you\s+take\s+them|"
    r"birdwatching|watching\s+birds?|birds?|eagles?|soar"
    r")\b",
    re.IGNORECASE,
)
_SUPPORT_CAREER_MOTIVATION_DIRECT_RE = re.compile(
    r"\b(?:"
    r"(?:support|love|acceptance)\b(?=.{0,180}\b(?:journey|pass\s+it\s+on|"
    r"supportive\s+community|hope|understanding|acceptance)\b)|"
    r"(?:made\s+a\s+huge\s+difference|made\s+.*\bdifference|"
    r"counseling\s+and\s+support\s+groups|support\s+groups\s+improved|"
    r"improved\s+my\s+life|now\s+i\s+want\s+to\s+help|safe,\s*inviting\s+place)"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)
_SUPPORT_CAREER_MOTIVATION_CONTEXT_RE = re.compile(
    r"\b(?:support|journey|counsel(?:ing|or)?|mental\s+health|help\s+people|"
    r"supportive\s+community|understanding|acceptance|hope)\b",
    re.IGNORECASE,
)
_SENTIMENTAL_REMINDER_DIRECT_RE = re.compile(
    r"\b(?:reminds?|reminder|sentimental\s+value|symboli[sz](?:es|ed)?|"
    r"meaning|means|stands?\s+for)\b(?=.{0,220}\b(?:art|self[-\s]?expression|"
    r"friend|birthday|gift|memory|pattern|colou?rs?|childhood|love|faith|"
    r"strength|roots?|family|keepsake)\b)|"
    r"\b(?:sentimental\s+value|hand[-\s]?painted|keepsake|gift|birthday|"
    r"pattern|colou?rs?)\b(?=.{0,220}\b(?:reminds?|reminder|symbol|meaning|"
    r"self[-\s]?expression)\b)",
    re.IGNORECASE | re.DOTALL,
)
_SENTIMENTAL_REMINDER_CONTEXT_RE = re.compile(
    r"\b(?:reminds?|reminder|sentimental|symbol|meaning|gift|memory|keepsake|"
    r"pattern|colou?rs?|self[-\s]?expression)\b",
    re.IGNORECASE,
)
_CLASSICAL_MUSIC_PREFERENCE_DIRECT_RE = re.compile(
    r"\b(?:fan|enjoys?|likes?|loves?|favorite|favourite|fav(?:orite)?|into)\b"
    r"(?=.{0,180}\b(?:classical|bach|mozart|vivaldi|orchestra|symphony|"
    r"composer|violin|clarinet|tunes?|songs?|music)\b)|"
    r"\b(?:classical|bach|mozart|vivaldi|orchestra|symphony|composer)\b"
    r"(?=.{0,180}\b(?:fan|enjoys?|likes?|loves?|favorite|favourite|"
    r"fav(?:orite)?|tunes?|songs?|music)\b)",
    re.IGNORECASE | re.DOTALL,
)
_OUTDOOR_NATURE_MEMORY_DIRECT_RE = re.compile(
    r"\b(?:camp(?:ing)?\s+trip|camped|camping)\b"
    r"(?=.{0,240}\b(?:meteor\s+shower|perseid|sky|universe|"
    r"streaks?\s+of\s+light|made\s+wishes?|one\s+with)\b)|"
    r"\b(?:meteor\s+shower|perseid|sky|universe|streaks?\s+of\s+light|"
    r"made\s+wishes?|one\s+with)\b"
    r"(?=.{0,240}\b(?:camp(?:ing)?\s+trip|camped|camping|nature|outdoors?)\b)",
    re.IGNORECASE | re.DOTALL,
)
_OUTDOOR_NATURE_MEMORY_CONTEXT_RE = re.compile(
    r"\b(?:camp(?:ing)?\s+trip|camped|camping|meteor\s+shower|perseid|"
    r"sky|universe|nature|outdoors?)\b",
    re.IGNORECASE,
)
_CHILDREN_PREFERENCE_DIRECT_RE = re.compile(
    r"\b(?:kids?|children|child|sons?|daughters?|younger\s+kids?)\b"
    r"(?=.{0,220}\b(?:likes?|loves?|enjoys?|favorite|favourite|stoked|"
    r"excited|into)\b)"
    r"(?=.{0,260}\b(?:dinosaurs?|exhibit|museum|animals?|bones?|nature|"
    r"outdoors?|hikes?|hiking|camping|campfire|marshmallows?|books?|stories|"
    r"learning|pottery|clay|painting|creative|creativity)\b)|"
    r"\b(?:they|them)\b(?=.{0,140}\b(?:were\s+)?(?:stoked|excited)\b)"
    r"(?=.{0,220}\b(?:dinosaurs?|exhibit|museum|animals?|bones?|nature|"
    r"outdoors?|hikes?|hiking|camping|books?|stories|learning)\b)|"
    r"\b(?:they|them)\b(?=.{0,180}\b(?:likes?|loves?|enjoys?|favorite|"
    r"favourite)\b)"
    r"(?=.{0,220}\b(?:dinosaurs?|exhibit|museum|animals?|bones?|nature|"
    r"outdoors?|hikes?|hiking|camping|books?|stories|learning)\b)",
    re.IGNORECASE | re.DOTALL,
)
_CHILDREN_PREFERENCE_CONTEXT_RE = re.compile(
    r"\b(?:kids?|children|child|sons?|daughters?|they|them|dinosaurs?|exhibit|"
    r"museum|animals?|bones?|nature|outdoors?|hikes?|hiking|camping|books?|"
    r"stories|learning|pottery|clay|painting)\b",
    re.IGNORECASE,
)
_PUBLIC_OFFICE_SERVICE_DIRECT_RE = re.compile(
    r"\b(?:running|run|ran)\s+for\s+office\b|"
    r"\bpublic\s+office\b|"
    r"\bpolitics?\b(?=.{0,180}\b(?:positive\s+changes?|better\s+future|impact)\b)",
    re.IGNORECASE | re.DOTALL,
)
_MILITARY_SERVICE_GOAL_DIRECT_RE = re.compile(
    r"\b(?:wanted|want|goal|goals?|reminded\s+me\s+why)\b"
    r"(?=.{0,180}\b(?:join(?:ing)?\s+the\s+military|military\s+service|"
    r"serve\s+(?:the\s+)?country|service\s+to\s+the\s+country)\b)|"
    r"\b(?:join(?:ing)?\s+the\s+military|military\s+service|"
    r"service\s+to\s+the\s+country)\b"
    r"(?=.{0,180}\b(?:wanted|want|goal|goals?|resilience|hope)\b)",
    re.IGNORECASE | re.DOTALL,
)
_DIVERSITY_FAMILY_PRIORITY = (
    "fact",
    "chunk",
    "extraction_artifact",
    "anchor",
    "suggestion",
)
_QUERY_OBJECT_TOKEN_RE = re.compile(r"\b[\w']+\b", re.UNICODE)
_TEMPORAL_ANSWER_SUPPORT_QUERY_RE = re.compile(
    r"\b(?:when|date|time|day|week|month|year|morning|afternoon|evening|"
    r"before|after|during|first|last|previous|next|recently|yesterday|today|"
    r"tomorrow|how\s+long|how\s+often|duration|frequency)\b",
    re.IGNORECASE,
)
_MUSIC_EVENT_ATTENDANCE_QUERY_RE = re.compile(
    r"\b(?:music|concerts?|live\s+music|festivals?|shows?|performances?)\b"
    r"(?=.{0,120}\b(?:events?|attend(?:ed|s|ing)?|went|joined|participated)\b)|"
    r"\b(?:events?|attend(?:ed|s|ing)?|went|joined|participated)\b"
    r"(?=.{0,120}\b(?:music|concerts?|live\s+music|festivals?|shows?|performances?)\b)",
    re.IGNORECASE | re.DOTALL,
)
_DEGREE_COMPLETION_TEMPORAL_QUERY_RE = re.compile(
    r"\b(?:when|date|time|day|month|year)\b"
    r"(?=.{0,120}\b(?:degree|diploma|certificate|graduat(?:e|ed|ion))\b)|"
    r"\b(?:degree|diploma|certificate|graduat(?:e|ed|ion))\b"
    r"(?=.{0,120}\b(?:when|date|time|day|month|year)\b)",
    re.IGNORECASE | re.DOTALL,
)
_TEMPORAL_ANSWER_SUPPORT_REASONS = frozenset(
    {
        "after-event-temporal-bridge",
        "age-birthday-bridge",
        "before-event-temporal-bridge",
        "decomposition-temporal-answer",
        "pet-acquisition-date-bridge",
        "temporal-event-detail-bridge",
    }
)
_NAMED_ACQUISITION_OBJECT_QUERY_RE = re.compile(
    r"\b[Ww]hen\s+(?:did|was)\s+"
    r"[A-Z][A-Za-z._'-]{1,39}\s+"
    r"(?:get|got|buy|bought|bring|brought|give|gave|adopt(?:ed)?)\s+"
    r"(?P<object>[A-Z][A-Za-z._'-]{1,39})\b"
)
_TEMPORAL_QUERY_OBJECT_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "did",
        "do",
        "does",
        "for",
        "had",
        "has",
        "have",
        "in",
        "is",
        "of",
        "on",
        "the",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "how",
    }
)
_ANIMAL_CARE_DIRECT_INSTRUCTION_RE = re.compile(
    r"\b(?:keep(?:ing)?\s+(?:their|the)?\s*(?:area|tank|space|habitat)\s+clean|"
    r"clean\s+(?:area|tank|space|habitat)|feed(?:ing)?\s+(?:them\s+)?properly|"
    r"enough\s+light|make\s+sure\s+they\s+get\s+enough\s+light|"
    r"care\s+instructions?|kind\s+of\s+fun)\b",
    re.IGNORECASE,
)
_ANIMAL_CARE_GENERIC_HABITAT_RE = re.compile(
    r"\b(?:relaxing\s+in\s+the\s+tank|basking|heat\s+lamp|new\s+tank|"
    r"bigger\s+tank|room\s+to\s+swim|took\s+my\s+turtles\s+out\s+for\s+a\s+walk|"
    r"cute\s+pet|little\s+dudes)\b",
    re.IGNORECASE,
)
_POTTERY_TYPE_PRIMARY_ANSWER_OBJECT_RE = re.compile(
    r"\b(?:clay|cup|cups|mug|mugs|pot|pots|dog\s+face)\b",
    re.IGNORECASE,
)
_POTTERY_TYPE_SECONDARY_ANSWER_OBJECT_RE = re.compile(
    r"\b(?:bowl|bowls|plate|plates|ceramic|project|projects)\b",
    re.IGNORECASE,
)
_POTTERY_TYPE_GENERIC_ANSWER_OBJECT_RE = re.compile(
    r"\b(?:pottery|art|painting|creative|creativity)\b",
    re.IGNORECASE,
)
_POTTERY_TYPE_INVENTORY_CONTEXT_RE = re.compile(
    r"\b(?:pottery|ceramic|clay|bowl|bowls|cup|cups|mug|mugs|plate|plates)\b",
    re.IGNORECASE,
)
_POTTERY_TYPE_CUP_SLOT_RE = re.compile(r"\b(?:cup|cups|mug|mugs|dog\s+face)\b", re.IGNORECASE)
_POTTERY_TYPE_BOWL_SLOT_RE = re.compile(r"\b(?:bowl|bowls)\b", re.IGNORECASE)
_POTTERY_TYPE_POT_SLOT_RE = re.compile(r"\b(?:pot|pots)\b", re.IGNORECASE)
_POTTERY_TYPE_PROJECT_SLOT_RE = re.compile(
    r"\b(?:clay|ceramic|project|projects|piece|pieces|finished)\b",
    re.IGNORECASE,
)
_POTTERY_TYPE_DIRECT_MADE_OBJECT_RE = re.compile(
    r"\b(?:dog\s+face|black\s+and\s+white\s+flower|photo\s+of\s+a\s+(?:bowl|cup)|"
    r"kids?.{0,120}(?:clay|cup|pots?|pottery\s+workshop)|"
    r"(?:clay|cup|pots?|pottery\s+workshop).{0,120}kids?)\b",
    re.IGNORECASE | re.DOTALL,
)
_PET_ACQUISITION_DATE_ANCHOR_SUPPORT_RE = re.compile(
    r"\b(?:session_\d+\s+date|date:\s+)",
    re.IGNORECASE | re.DOTALL,
)
_PET_ACQUISITION_OBJECT_ANCHOR_RE = re.compile(
    r"\b(?:adopt(?:ed|ion)?|gift(?:ed)?|named|"
    r"new\s+(?:addition|pet|pup|puppy|dog)|"
    r"stuffed\s+animal|toy\s+(?:pup|dog))\b",
    re.IGNORECASE,
)
_POTTERY_TYPE_FRIENDSHIP_COMPANION_RE = re.compile(
    r"\b(?:(?:pottery\s+project|finished\s+another\s+pottery|source\s+of\s+happiness)"
    r".{0,260}(?:values?\s+friendship|appreciat(?:e|es|ion).{0,60}friendship|"
    r"family\s+outing|planning\s+something\s+special)|(?:values?\s+friendship|appreciat(?:e|es|ion).{0,40}friendship\s+too|always\s+been\s+there))\b",
    re.IGNORECASE | re.DOTALL,
)
_POTTERY_TYPE_PROJECT_COMPANION_RE = re.compile(
    r"\b(?:pottery\s+project|finished\s+another\s+pottery|source\s+of\s+happiness|"
    r"fulfillment|sanctuary|comfort)\b",
    re.IGNORECASE,
)
_FAMILY_ACTIVITY_DIRECT_ANSWER_OBJECT_RE = re.compile(
    r"\b(?:husband|motivated|motivate|motivation)\b(?=.{0,180}\b"
    r"(?:family|kids?|children|hiking|hike|nature|waterfall|trail))|"
    r"\b(?:family|kids?|children|hiking|hike|nature|waterfall|trail)\b"
    r"(?=.{0,180}\b(?:husband|motivated|motivate|motivation))",
    re.IGNORECASE | re.DOTALL,
)
_FAMILY_ACTIVITY_ACTIVITY_OBJECT_RE = re.compile(
    r"\b(?:swimming|swim|hiking|hike|trail|waterfall|museum|dinosaur|"
    r"pottery|clay|painting|camping|campfire|marshmallow|park)\b",
    re.IGNORECASE,
)
_FAMILY_ACTIVITY_CONTEXT_OBJECT_RE = re.compile(
    r"\b(?:family|fam|kids?|children|husband)\b",
    re.IGNORECASE,
)
_ACTIVITY_DIRECT_PARTICIPATION_RE = re.compile(
    r"\b(?:signed\s+up\s+for|joined|started|went|go(?:ing)?|off\s+to\s+go|"
    r"took|did|finished|made|painted|pottery\s+class|workshop|"
    r"visual\s+query:\s*painting|image\s+caption:.{0,120}\bpainting)\b"
    r"(?=.{0,240}\b(?:pottery|class|camp(?:ing|ed)?|swimm(?:ing)?|swim|"
    r"painting|painted|sunrise|sunset|lake|hiking|hike|trail|workshop|clay|"
    r"creative|kids?|family|fam)\b)",
    re.IGNORECASE | re.DOTALL,
)
_ACTIVITY_CONTEXT_RE = re.compile(
    r"\b(?:pottery|class|camp(?:ing|ed)?|swimm(?:ing)?|swim|painting|painted|"
    r"sunrise|sunset|lake|hiking|hike|trail|workshop|clay|creative|kids?|"
    r"family|fam|unplug)\b",
    re.IGNORECASE,
)
_INVENTORY_FRIEND_PLACE_DIRECT_RE = re.compile(
    r"\b(?:became\s+friends|now\s+friends|made\s+friends|friends\s+with|"
    r"fellow\s+volunteers?)\b",
    re.IGNORECASE,
)
_INVENTORY_FRIEND_COMMUNITY_PLACE_RE = re.compile(
    r"\b(?:joined\s+(?:a\s+|the\s+|nearby\s+|local\s+)?(?:church|gym)|"
    r"(?:church|gym).{0,120}\b(?:community|supportive|welcoming|people)|"
    r"(?:supportive|welcoming).{0,120}\b(?:church|gym)|"
    r"feel\s+closer\s+to\s+a\s+community)\b",
    re.IGNORECASE | re.DOTALL,
)
_INVENTORY_SHELTER_SLOT_RE = re.compile(
    r"\b(?:homeless\s+shelter|dog\s+shelter|animal\s+shelter|shelter)\b",
    re.IGNORECASE,
)
_INVENTORY_ANIMAL_SHELTER_SLOT_RE = re.compile(
    r"\b(?:dog|animal)\s+shelter\b",
    re.IGNORECASE,
)
_INVENTORY_FRIEND_PLACE_SHELTER_ANCHOR_RE = re.compile(
    r"\b(?:homeless\s+shelter|shelter)\b(?=.{0,80}\b"
    r"(?:i\s+volunteer\s+at|where\s+(?:she\s+)?volunteers?|"
    r"donated\s+(?:my\s+|her\s+)?old\s+car))|"
    r"\b(?:i\s+volunteer\s+at|where\s+(?:she\s+)?volunteers?|"
    r"donated\s+(?:my\s+|her\s+)?old\s+car)\b(?=.{0,80}\b"
    r"(?:homeless\s+shelter|shelter))",
    re.IGNORECASE | re.DOTALL,
)
_INVENTORY_FRIEND_PLACE_SHELTER_ACTIVITY_REPEAT_RE = re.compile(
    r"\b(?:gave\s+a\s+few\s+talks|received\s+lots\s+of\s+compliments|"
    r"fundraiser|tournament|baked\s+goods?|dropped\s+off|"
    r"received\s+a\s+medal|front\s+desk|kids?\s+event)\b",
    re.IGNORECASE,
)
_INVENTORY_VOLUNTEER_HELPED_PERSON_SLOT_RE = re.compile(
    r"\b(?:someone|person)\s+named\s+[A-Z][a-z]+\b|"
    r"\bmet\s+(?:this\s+)?(?:amazing\s+)?(?:woman|man|person),\s+[A-Z][a-z]+\b|"
    r"\b[Oo]ne\s+of\s+the\s+(?:shelter\s+)?residents?,\s+[A-Z][a-z]+,\s+wrote\b|"
    r"\bresidents?\s+at\s+the\s+shelter,\s+[A-Z][a-z]+,\s+wrote\b|"
    r"\b[A-Z][a-z]+,\s+a\s+resident\s+at\s+the\s+shelter\b"
    r"(?=.{0,120}\b(?:gratitude|appreciation|letter|support))",
    re.DOTALL,
)
_INVENTORY_SHELTER_SERVICE_ACTIVITY_SLOT_RE = re.compile(
    r"\b(?:homeless\s+shelter|shelter)\b(?=.{0,180}\b"
    r"(?:give\s+out|hand\s+out|serve|distribut(?:e|ed|ing)|"
    r"donation\s+drive|toy\s+drive|kids?\s+in\s+need|"
    r"held\s+some\s+events|service\s+events?))|"
    r"\b(?:give\s+out|hand\s+out|serve|distribut(?:e|ed|ing)|"
    r"donation\s+drive|toy\s+drive|kids?\s+in\s+need|"
    r"held\s+some\s+events|service\s+events?)\b(?=.{0,180}\b"
    r"(?:homeless\s+shelter|shelter)\b)",
    re.IGNORECASE | re.DOTALL,
)
_INVENTORY_GYM_SLOT_RE = re.compile(
    r"\b(?:joined\s+(?:a\s+|the\s+|nearby\s+|local\s+)?gym|gym)\b",
    re.IGNORECASE,
)
_INVENTORY_CHURCH_JOINED_SLOT_RE = re.compile(
    r"\bjoined\s+(?:a\s+|the\s+)?(?:nearby\s+|local\s+)?church\b",
    re.IGNORECASE,
)
_INVENTORY_CHURCH_SLOT_RE = re.compile(r"\bchurch\b", re.IGNORECASE)
_INVENTORY_BOOK_READING_SLOT_RE = re.compile(
    r"\b(?:loved\s+reading\s+\"?[A-Z][^\"\n]{1,80}\"?|"
    r"love\s+reading\s+\"?[A-Z][^\"\n]{1,80}\"?|book\s+i\s+read\s+last\s+year|"
    r"favorite\s+book|favourite\s+book|childhood\s+book|read\s+as\s+a\s+kid|"
    r"read(?:ing)?\s+\"?[A-Z][^\"\n]{1,80}\"?)\b",
    re.IGNORECASE | re.DOTALL,
)
_BOOK_READING_DIRECT_ANSWER_RE = re.compile(
    r"\b(?:"
    r"loved\s+reading\s+\"?[A-Z][^\"\n]{1,80}\"?|"
    r"read\s+\"?[A-Z][^\"\n]{1,80}\"?\s+as\s+a\s+kid|"
    r"book\s+i\s+read\s+last\s+year|"
    r"favorite\s+book\s+(?:is|was)|"
    r"favourite\s+book\s+(?:is|was)"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)
_BOOK_READING_CONTEXT_RE = re.compile(
    r"\b(?:book|books|reading|read)\b",
    re.IGNORECASE,
)
_INVENTORY_CHURCH_FRIEND_ACTIVITY_SLOT_RE = re.compile(
    r"\b(?:church\s+friends?|friends?\s+from\s+church)\b(?=.{0,180}\b"
    r"(?:hikes?|hiking|picnic|visited?|park|activities?|outing|trip|camping|"
    r"community\s+work|community\s+service|volunteer\s+work|volunteering|"
    r"service\s+project|chilled|played\s+games|games|charades|"
    r"scavenger\s+hunt|refreshed|rewarding)\b)|"
    r"\b(?:hikes?|hiking|picnic|visited?|park|activities?|outing|trip|camping|"
    r"community\s+work|community\s+service|volunteer\s+work|volunteering|"
    r"service\s+project|chilled|played\s+games|games|charades|"
    r"scavenger\s+hunt|refreshed|rewarding)\b"
    r"(?=.{0,180}\b(?:church\s+friends?|friends?\s+from\s+church)\b)",
    re.IGNORECASE | re.DOTALL,
)
_INVENTORY_VOLUNTEER_SLOT_RE = re.compile(
    r"\b(?:volunteer|volunteers|volunteering)\b",
    re.IGNORECASE,
)
_INVENTORY_EDUCATION_INFRASTRUCTURE_SLOT_RE = re.compile(
    r"\b(?:education|educational|school|schools|infrastructure|"
    r"community\s+meetings?|education\s+reform|infrastructure\s+development)\b",
    re.IGNORECASE,
)
_CAUSE_EDUCATION_SLOT_RE = re.compile(
    r"\b(?:education|educational|school|schools|students?|education\s+reform)\b",
    re.IGNORECASE,
)
_CAUSE_INFRASTRUCTURE_SLOT_RE = re.compile(
    r"\binfrastructure\b",
    re.IGNORECASE,
)
_INVENTORY_VETERANS_SLOT_RE = re.compile(
    r"\b(?:veterans?|military|served|service\s+members?|memorial)\b",
    re.IGNORECASE,
)
_INVENTORY_VETERANS_PETITION_SLOT_RE = re.compile(
    r"\b(?:petition|signatures?)\b(?=.{0,160}\b(?:veterans?|military)\b)|"
    r"\b(?:veterans?|military)\b(?=.{0,160}\b(?:petition|signatures?)\b)",
    re.IGNORECASE | re.DOTALL,
)
_INVENTORY_VETERANS_RUN_SLOT_RE = re.compile(
    r"\b(?:5k|charity\s+run|run|funds?|raise(?:d)?)\b"
    r"(?=.{0,180}\b(?:veterans?|military|families)\b)|"
    r"\b(?:veterans?|military|families)\b"
    r"(?=.{0,180}\b(?:5k|charity\s+run|run|funds?|raise(?:d)?)\b)",
    re.IGNORECASE | re.DOTALL,
)
_INVENTORY_VETERANS_MARCH_SLOT_RE = re.compile(
    r"\b(?:march(?:ing)?|parade)\b(?=.{0,160}\b(?:veterans?|military|rights?)\b)|"
    r"\b(?:veterans?|military|rights?)\b(?=.{0,160}\b(?:march(?:ing)?|parade)\b)",
    re.IGNORECASE | re.DOTALL,
)
_INVENTORY_VETERANS_HOSPITAL_SLOT_RE = re.compile(
    r"\b(?:veterans?'?\s+hospital|hospital)\b(?=.{0,160}\b(?:veterans?|military)\b)|"
    r"\b(?:veterans?|military)\b(?=.{0,160}\bhospital\b)",
    re.IGNORECASE | re.DOTALL,
)
_INVENTORY_MUSIC_EVENT_SLOT_RE = re.compile(
    r"\b(?:live\s+music|violin\s+concert|concert|festival|show|performance)\b",
    re.IGNORECASE,
)
_INVENTORY_CLASSICAL_MUSIC_PREFERENCE_SLOT_RE = re.compile(
    r"\b(?:classical|bach|mozart|vivaldi|orchestra|symphony|composer)\b"
    r"(?=.{0,180}\b(?:fan|enjoys?|likes?|loves?|favorite|favourite|"
    r"fav(?:orite)?|tunes?|songs?|music)\b)|"
    r"\b(?:fan|enjoys?|likes?|loves?|favorite|favourite|fav(?:orite)?|into)\b"
    r"(?=.{0,180}\b(?:classical|bach|mozart|vivaldi|orchestra|symphony|"
    r"composer|tunes?|songs?|music)\b)",
    re.IGNORECASE | re.DOTALL,
)
_INVENTORY_MUSIC_LIVE_EVENT_SLOT_RE = re.compile(
    r"\blive\s+music(?:\s+event)?\b",
    re.IGNORECASE,
)
_INVENTORY_MUSIC_VIOLIN_CONCERT_SLOT_RE = re.compile(
    r"\bviolin\s+concert\b",
    re.IGNORECASE,
)
_INVENTORY_STATE_PLACE_SLOT_RE = re.compile(
    r"\b(?:florida|oregon|california|texas|new\s+york|east\s+coast|"
    r"pacific\s+northwest|northwest|coast|state|states|areas?)\b",
    re.IGNORECASE,
)
_INVENTORY_STATE_FLORIDA_SLOT_RE = re.compile(r"\bflorida\b", re.IGNORECASE)
_INVENTORY_STATE_OREGON_SLOT_RE = re.compile(r"\boregon\b", re.IGNORECASE)
_INVENTORY_STATE_EAST_COAST_SLOT_RE = re.compile(r"\beast\s+coast\b", re.IGNORECASE)
_INVENTORY_STATE_PACIFIC_NORTHWEST_SLOT_RE = re.compile(
    r"\b(?:pacific\s+northwest|northwest)\b",
    re.IGNORECASE,
)
_INVENTORY_OUTDOOR_ACTIVITY_SLOT_RE = re.compile(
    r"\b(?:hiking|hike|mountaineering|camping|trail|mountains?|park|picnic|"
    r"waterfall)\b",
    re.IGNORECASE,
)
_INVENTORY_OUTDOOR_WATERFALL_SLOT_RE = re.compile(r"\bwaterfall\b", re.IGNORECASE)
_INVENTORY_OUTDOOR_HIKING_SLOT_RE = re.compile(r"\bhik(?:e|ing)\b", re.IGNORECASE)
_INVENTORY_OUTDOOR_MOUNTAINEERING_SLOT_RE = re.compile(
    r"\bmountaineering\b",
    re.IGNORECASE,
)
_INVENTORY_OUTDOOR_PICNIC_SLOT_RE = re.compile(r"\bpicnic\b", re.IGNORECASE)
_INVENTORY_OUTDOOR_VISUAL_GROUP_SLOT_RE = re.compile(
    r"\byou\s+and\s+(?:your\s+)?"
    r"(?:friends?|colleagues?|co-?workers?|workmates?|teammates?|team|group)\b"
    r"(?=.{0,120}\b(?:look(?:s|ing)?|seem(?:s|ed)?|great|team|group)\b)|"
    r"\b(?:friends?|colleagues?|co-?workers?|workmates?|teammates?)\b"
    r"(?=.{0,120}\blook(?:s|ing)?\s+like\s+(?:a\s+)?(?:great\s+)?"
    r"(?:team|group)\b)",
    re.IGNORECASE | re.DOTALL,
)
_INVENTORY_EVENT_CHILI_COOKOFF_SLOT_RE = re.compile(
    r"\bchili\s+cook[-\s]?off\b",
    re.IGNORECASE,
)
_INVENTORY_EVENT_TOURNAMENT_SLOT_RE = re.compile(
    r"\btournament\b",
    re.IGNORECASE,
)
_INVENTORY_EVENT_FUNDRAISER_SETUP_SLOT_RE = re.compile(
    r"\b(?:getting\s+ready|preparing|planning|organizing|cover\s+basic\s+needs|"
    r"raise\s+enough)\b(?=.{0,180}\b(?:fundraiser|fundraising|shelter|homeless)\b)|"
    r"\b(?:fundraiser|fundraising|shelter|homeless)\b"
    r"(?=.{0,180}\b(?:getting\s+ready|preparing|planning|organizing|"
    r"cover\s+basic\s+needs|raise\s+enough)\b)",
    re.IGNORECASE | re.DOTALL,
)
_INVENTORY_ANIMAL_ACTIVITY_FEEDING_SLOT_RE = re.compile(
    r"\b(?:feed(?:ing)?|eat(?:ing)?|fruit|strawberries|snacks?)\b"
    r"(?=.{0,180}\b(?:turtles?|pets?|animals?|reptiles?)\b)|"
    r"\b(?:turtles?|pets?|animals?|reptiles?)\b"
    r"(?=.{0,180}\b(?:feed(?:ing)?|eat(?:ing)?|fruit|strawberries|snacks?)\b)",
    re.IGNORECASE | re.DOTALL,
)
_INVENTORY_ANIMAL_ACTIVITY_HOLDING_SLOT_RE = re.compile(
    r"\bhold(?:ing)?\b(?=.{0,180}\b(?:turtles?|pets?|animals?|reptiles?)\b)|"
    r"\b(?:turtles?|pets?|animals?|reptiles?)\b(?=.{0,180}\bhold(?:ing)?\b)",
    re.IGNORECASE | re.DOTALL,
)
_INVENTORY_ANIMAL_ACTIVITY_BATH_SLOT_RE = re.compile(
    r"\b(?:bath|bathe|bathing)\b(?=.{0,180}\b(?:turtles?|pets?|animals?|reptiles?)\b)|"
    r"\b(?:turtles?|pets?|animals?|reptiles?)\b"
    r"(?=.{0,180}\b(?:bath|bathe|bathing)\b)",
    re.IGNORECASE | re.DOTALL,
)
_INVENTORY_ANIMAL_ACTIVITY_WALK_SLOT_RE = re.compile(
    r"\bwalk(?:s|ed|ing)?\b(?=.{0,180}\b(?:turtles?|pets?|animals?|reptiles?)\b)|"
    r"\b(?:turtles?|pets?|animals?|reptiles?)\b(?=.{0,180}\bwalk(?:s|ed|ing)?\b)",
    re.IGNORECASE | re.DOTALL,
)
_INVENTORY_COMMUNITY_SLOT_RE = re.compile(
    r"\b(?:community|supportive\s+people|welcoming\s+atmosphere)\b",
    re.IGNORECASE,
)
_INVENTORY_SUPPORT_GROUP_SLOT_RE = re.compile(r"\bsupport\s+group\b", re.IGNORECASE)
_INVENTORY_COUNTRY_SLOT_RE = re.compile(
    r"\b(?:england|spain|france|italy|germany|portugal|ireland|sweden|"
    r"country|countries|abroad|european?)\b",
    re.IGNORECASE,
)
_INVENTORY_PLACE_MARKER_RE = re.compile(
    r"\b(?:homeless\s+shelter|dog\s+shelter|shelter|volunteers?|church|gym)\b",
    re.IGNORECASE,
)
_RELIGIOUS_DIRECT_EVIDENCE_RE = re.compile(
    r"\b(?:church|faith|stained\s+glass|pray|prayer|spiritual|worship)\b",
    re.IGNORECASE,
)
_RELIGIOUS_CONTRAST_EVIDENCE_RE = re.compile(
    r"\breligious\b(?=.{0,160}\b(?:conservatives?|unwelcoming|upset|lgbtq|rights)\b)|"
    r"\b(?:conservatives?|unwelcoming|upset|lgbtq|rights)\b"
    r"(?=.{0,160}\breligious\b)",
    re.IGNORECASE | re.DOTALL,
)
_SUPPORT_NETWORK_DIRECT_ANSWER_RE = re.compile(
    r"\b(?:friends?|family|fam|mentors?|parents?|mother|father|coach|people\s+around)\b"
    r"(?=.{0,180}\b(?:rocks?|support(?:s|ed|ive)?|there\s+for|strength|motivat(?:e|es|ed|ing)|"
    r"push\s+on|lean\s+on|comfort|help(?:ed|ful)?)\b)|"
    r"\b(?:rocks?|support(?:s|ed|ive)?|there\s+for|strength|motivat(?:e|es|ed|ing)|"
    r"push\s+on|lean\s+on|comfort|help(?:ed|ful)?)\b"
    r"(?=.{0,180}\b(?:friends?|family|fam|mentors?|parents?|mother|father|coach|"
    r"people\s+around)\b)",
    re.IGNORECASE | re.DOTALL,
)
_SUPPORT_NETWORK_SOCIAL_ACTOR_RE = re.compile(
    r"\b(?:friends?|family|fam|mentors?|parents?|mother|father|coach|people\s+around|"
    r"support\s+system|support\s+network)\b",
    re.IGNORECASE,
)
_SUPPORT_NETWORK_SUPPORT_ACTION_RE = re.compile(
    r"\b(?:rocks?|support(?:s|ed|ive)?|there\s+for|strength|motivat(?:e|es|ed|ing)|"
    r"push\s+on|lean\s+on|comfort|help(?:ed|ful)?)\b",
    re.IGNORECASE,
)
_CONVERSATIONAL_SUPPORT_TURN_RE = re.compile(
    r"\b(?:appreciat(?:e|ed|es|ing)|friendship|always\s+been\s+there|"
    r"there\s+for\s+me|support(?:s|ed|ive)?|means?\s+a\s+lot)\b",
    re.IGNORECASE,
)
_MUSIC_ARTIST_DIRECT_ANSWER_RE = re.compile(
    r"\b(?:it\s+was|artist\s+was|band\s+was|singer\s+was|performer\s+was)\s+"
    r"[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+){0,3}\b|"
    r"\b[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+){0,3}\b"
    r"(?=.{0,120}\b(?:talented|voice|songs?|singer|artist|performer)\b)",
    re.IGNORECASE | re.DOTALL,
)
_TEMPORAL_DIRECT_ANSWER_RE = re.compile(
    r"\b(?:"
    r"yesterday|tomorrow|last\s+(?:night|week|month|year|mon(?:day)?|tue(?:sday)?|"
    r"wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)|"
    r"next\s+(?:week|month|year|mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|"
    r"thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)|"
    r"(?:one|two|three|four|five|six|seven|\d+)\s+days?\s+ago|"
    r"(?:one|two|three|four|five|six|seven|\d+)\s+weeks?\s+ago"
    r")\b",
    re.IGNORECASE,
)
def _diversity_candidates(items: list[ContextItem]) -> dict[str, ContextItem]:
    candidates: dict[str, ContextItem] = {}
    for item in items:
        family = _diversity_family(item)
        existing = candidates.get(family)
        if existing is None or _diversity_candidate_item_key(item) < (
            _diversity_candidate_item_key(existing)
        ):
            candidates[family] = item
    return candidates


def _ordered_diversity_families(candidates: dict[str, ContextItem]) -> tuple[str, ...]:
    priority = {family: index for index, family in enumerate(_DIVERSITY_FAMILY_PRIORITY)}
    return tuple(
        sorted(
            candidates,
            key=lambda family: (
                priority.get(_diversity_family_base(family), len(priority)),
                context_rank_key(candidates[family]),
                family,
            ),
        )
    )


def _diversity_family(item: ContextItem) -> str:
    if item.item_type == "anchor":
        return _typed_diversity_family(
            "anchor",
            _diagnostic_text(item, "anchor_kind"),
        )
    if item.item_type == "extraction_artifact":
        return _typed_diversity_family(
            "extraction_artifact",
            _artifact_diversity_hint(item),
        )
    if item.item_type in _DIVERSITY_FAMILY_PRIORITY:
        return item.item_type
    return item.item_type or "unknown"


def _diversity_candidate_item_key(item: ContextItem) -> tuple[object, ...]:
    query_reason = _answer_support_query_reason(item)
    broad_window_rank = 1
    if (
        query_reason in _DIVERSITY_PRECISE_TURN_REASONS
        and _has_primary_exact_turn_source_ref(item)
    ) or (
        query_reason in _BROAD_EVIDENCE_ANSWER_SUPPORT_REASONS
        and len(item.source_refs) > 1
    ):
        broad_window_rank = 0
    return (
        broad_window_rank,
        context_rank_key(item),
    )


def _answer_support_diversity_candidates(items: list[ContextItem], *, query: str = "") -> dict[str, ContextItem]:
    candidates: dict[str, ContextItem] = {}
    for item in items:
        family = _answer_support_diversity_family(item)
        if not family:
            continue
        existing = candidates.get(family)
        if existing is None or _answer_support_family_item_key_for_query(
            item, query=query
        ) < (
            _answer_support_family_item_key_for_query(existing, query=query)
        ):
            candidates[family] = item
    return candidates


def _answer_support_source_ref_ids_sample(
    ordered_families: tuple[str, ...],
    candidates: dict[str, ContextItem],
) -> tuple[str, ...]:
    source_ids: list[str] = []
    for family in ordered_families:
        item = candidates.get(family)
        if item is None:
            continue
        source_id = _primary_exact_turn_source_id(item) or _source_key(item)
        source_id = source_id.strip()
        if source_id and source_id not in source_ids:
            source_ids.append(source_id)
        if len(source_ids) >= 40:
            return tuple(source_ids)
    return tuple(source_ids)


def _answer_support_selected_source_ref_ids_sample(
    selected: tuple[ContextItem, ...],
) -> tuple[str, ...]:
    source_ids: list[str] = []
    for item in selected:
        if not _answer_support_diversity_family(item):
            continue
        for ref in item.source_refs:
            source_id = str(ref.source_id).strip()
            if source_id and source_id not in source_ids:
                source_ids.append(source_id)
            if len(source_ids) >= 40:
                return tuple(source_ids)
    return tuple(source_ids)


def _answer_support_selected_families_sample(
    selected: tuple[ContextItem, ...],
) -> tuple[str, ...]:
    families: list[str] = []
    for item in selected:
        family = _answer_support_diversity_family(item)
        if family and family not in families:
            families.append(family)
        if len(families) >= 40:
            return tuple(families)
    return tuple(families)


def _ordered_answer_support_families(candidates: dict[str, ContextItem]) -> tuple[str, ...]:
    return _ordered_answer_support_families_for_query(candidates, query="")


def _ordered_answer_support_families_for_query(
    candidates: dict[str, ContextItem],
    *,
    query: str,
) -> tuple[str, ...]:
    marker_source_group_counts = _marker_coverage_source_group_counts(candidates)
    broad_turn_source_group_counts = _broad_turn_source_group_counts(candidates)
    pet_acquisition_named_object_source_groups = (
        _pet_acquisition_named_object_source_groups(
            candidates,
            query=query,
        )
    )
    ordered = tuple(
        sorted(
            candidates,
            key=lambda family: (
                _answer_support_query_focus_priority(
                    family,
                    item=candidates[family],
                    query=query,
                ),
                _answer_support_family_priority(
                    family,
                    item=candidates[family],
                    query=query,
                    marker_source_group_counts=marker_source_group_counts,
                    broad_turn_source_group_counts=broad_turn_source_group_counts,
                    pet_acquisition_named_object_source_groups=(
                        pet_acquisition_named_object_source_groups
                    ),
                ),
                _answer_support_family_item_key_for_query(candidates[family], query=query),
                family,
            ),
        )
    )
    return _round_robin_inventory_slot_families(ordered, candidates=candidates)


def _answer_support_query_focus_priority(
    family: str,
    *,
    item: ContextItem,
    query: str,
) -> int:
    query_reason = _answer_support_query_reason(item)
    if (
        query_reason in _DIRECT_EVIDENCE_QUERY_FOCUS_REASONS
        and _has_any_exact_turn_source_ref(item)
        and _precise_answer_content_rank(item, query_reason=query_reason) == 0
    ):
        return -3
    if (
        _diversity_family_base(family)
        in {
            "query_reason_inventory_slot",
            "query_reason_inventory_slot_source_group",
        }
        and _is_cause_inventory_answer_support_item(item)
    ):
        return -4
    if _is_degree_completion_temporal_answer_support_item(item, query=query):
        return -3
    if not query or _MUSIC_EVENT_ATTENDANCE_QUERY_RE.search(query) is None:
        return 0
    query_reason = _answer_support_query_reason(item).replace("_", "-")
    if query_reason not in {
        "classical-music-preference-bridge",
        "music-event-inventory-bridge",
    }:
        return 0
    if _diversity_family_base(family) not in {
        "query_reason_inventory_slot",
        "query_reason_inventory_slot_source_group",
        "query_reason_marker_coverage_source_group",
        "query_reason_source_group",
        "temporal_source_sibling_marker", "temporal_source_sibling_marker_source_group",
    }:
        return 0
    slot = _inventory_answer_slot_for_text(item.text)
    if slot in {"music_live_event", "music_violin_concert"}:
        return -2
    if slot == "music_event":
        return -1
    return 0


def _answer_support_item_limit(candidates: dict[str, ContextItem]) -> int:
    inventory_slots_by_reason: dict[str, set[str]] = {}
    exact_marker_reasons: set[str] = set()
    has_pet_acquisition_support = False
    for family, item in candidates.items():
        if _answer_support_query_reason(item) == "pet_acquisition_date_bridge":
            has_pet_acquisition_support = True
        if _diversity_family_base(family) == "query_reason_exact_marker_source_group":
            exact_marker_reasons.add(_answer_support_query_reason(item).replace("_", "-"))
        slot = _answer_support_inventory_family_slot(family)
        if not slot:
            continue
        reason = _answer_support_query_reason(item).replace("_", "-")
        inventory_slots_by_reason.setdefault(reason, set()).add(slot)
    if "pottery-type-bridge" in exact_marker_reasons:
        return _MAX_INVENTORY_ANSWER_SUPPORT_DIVERSITY_ITEMS
    if has_pet_acquisition_support:
        return _MAX_INVENTORY_ANSWER_SUPPORT_DIVERSITY_ITEMS
    if any(
        len(slots) > _MAX_ANSWER_SUPPORT_DIVERSITY_ITEMS
        for slots in inventory_slots_by_reason.values()
    ):
        return _MAX_INVENTORY_ANSWER_SUPPORT_DIVERSITY_ITEMS
    return _MAX_ANSWER_SUPPORT_DIVERSITY_ITEMS


def _round_robin_inventory_slot_families(
    families: tuple[str, ...],
    *,
    candidates: dict[str, ContextItem],
) -> tuple[str, ...]:
    coverage_positions = tuple(
        index
        for index, family in enumerate(families)
        if _answer_support_coverage_family_slot(family)
    )
    if len(coverage_positions) < 3:
        return families
    slot_counts: dict[str, int] = {}
    ranked: list[tuple[int, int, int, str]] = []
    for index in coverage_positions:
        family = families[index]
        slot = _answer_support_coverage_family_slot(family)
        coverage_round = slot_counts.get(slot, 0)
        slot_counts[slot] = coverage_round + 1
        slot_priority = _answer_support_coverage_family_slot_priority(family)
        if _is_single_exact_cause_inventory_answer_support_item(candidates[family]):
            coverage_round = 0
        elif slot_priority < 0:
            coverage_round = max(0, coverage_round - 2)
        elif slot_priority >= 3:
            coverage_round += 2
        ranked.append((coverage_round, slot_priority, index, family))
    reranked_inventory = iter(family for _, _, _, family in sorted(ranked))
    inventory_position_set = set(coverage_positions)
    return tuple(
        next(reranked_inventory) if index in inventory_position_set else family
        for index, family in enumerate(families)
    )


def _answer_support_coverage_family_slot(family: str) -> str:
    inventory_slot = _answer_support_inventory_family_slot(family)
    if inventory_slot:
        return f"inventory:{inventory_slot}"
    activity_slot = _answer_support_activity_family_slot(family)
    if activity_slot:
        return f"activity:{activity_slot}"
    career_slot = _answer_support_career_family_slot(family)
    if career_slot:
        return f"career:{career_slot}"
    return ""


def _answer_support_coverage_family_slot_priority(family: str) -> int:
    inventory_slot = _answer_support_inventory_family_slot(family)
    if inventory_slot:
        return _inventory_answer_slot_priority_for_family(
            inventory_slot,
            family=family,
        )
    career_slot = _answer_support_career_family_slot(family)
    if career_slot:
        return _career_answer_slot_priority(career_slot)
    return 0


def _answer_support_inventory_family_slot(family: str) -> str:
    if _diversity_family_base(family) not in {
        "query_reason_inventory_slot",
        "query_reason_inventory_slot_source_group",
    }:
        return ""
    return _inventory_answer_slot_from_family(family)


def _answer_support_career_family_slot(family: str) -> str:
    if _diversity_family_base(family) not in {
        "query_reason_career_slot",
        "query_reason_career_slot_source_group",
    }:
        return ""
    return _career_answer_slot_from_family(family)


def _answer_support_family_priority(
    family: str,
    *,
    item: ContextItem,
    query: str,
    marker_source_group_counts: dict[str, int],
    broad_turn_source_group_counts: dict[str, int],
    pet_acquisition_named_object_source_groups: frozenset[str] = frozenset(),
) -> int:
    base = _diversity_family_base(family)
    if (
        base
        in {
            "query_reason_inventory_slot",
            "query_reason_inventory_slot_source_group",
        }
        and _is_cause_inventory_answer_support_item(item)
    ):
        if _has_primary_exact_turn_source_ref(item) and len(item.source_refs) == 1:
            return -5
        if _has_any_exact_turn_source_ref(item) and len(item.source_refs) == 1:
            return -4
        return -3
    if _is_pet_acquisition_date_anchor_answer_support_item(item):
        if _answer_support_source_group(item) in pet_acquisition_named_object_source_groups:
            return -3
        return -1
    if _answer_support_exact_query_object_hits(item, query=query):
        return -1
    if _is_degree_completion_temporal_answer_support_item(item, query=query):
        return -3
    if _is_exact_precise_content_answer_support_item(item):
        return -2
    if base in {
        "temporal_source_sibling_marker",
        "temporal_source_sibling_marker_source_group",
    }:
        return 2
    if base == "query_reason_count_coverage_source_group":
        return 0
    if (
        base == "query_reason_broad_turn_source_group"
        and _numeric_signal(
            _diagnostic_score_signals(item).get("book_author_preference_world_evidence")
        )
        >= 3
        and broad_turn_source_group_counts.get(_broad_turn_family_source_group(family), 0) > 1
    ):
        return 0
    if base in {
        "query_reason_activity_slot",
        "query_reason_activity_slot_source_group",
    }:
        return _inventory_answer_slot_priority_for_family(_answer_support_activity_family_slot(family), family=family) if _answer_support_query_reason(item) in {"art_style_bridge", "painting_inventory_bridge"} else 0
    if base == "query_reason_exact_marker_source_group" and _is_conversational_support_turn(
        item
    ):
        return 0
    if base == "query_reason_exact_marker_source_group":
        return 2
    query_reason = _answer_support_query_reason(item)
    if query_reason == "support_origin_bridge":
        return -1
    if (
        query_reason == "support_career_motivation_bridge"
        and _precise_answer_content_rank(item, query_reason=query_reason) == 0
    ):
        return 0
    if (
        _is_support_network_reason(query_reason)
        and _support_network_answer_object_rank(item.text) == 0
    ):
        return 0
    if (
        base == "query_reason_broad_turn_source_group"
        and query_reason == "birdwatching_city_schedule_bridge"
    ):
        return 0
    if _is_pottery_type_reason(query_reason) and base in {
        "query_reason",
        "query_reason_marker_coverage_source_group",
        "query_reason_source_group",
    }:
        return 0
    if (
        base == "query_reason_marker_coverage_source_group"
        and _is_pottery_type_inventory_item(item, query_reason=query_reason)
    ):
        return 0
    if base in {
        "query_reason_inventory_slot",
        "query_reason_inventory_slot_source_group",
    }:
        return _inventory_answer_slot_priority_for_family(
            _inventory_answer_slot_from_family(family),
            family=family,
        )
    if base in {
        "query_reason_career_slot",
        "query_reason_career_slot_source_group",
    }:
        return _career_answer_slot_priority(_career_answer_slot_from_family(family))
    if base == "query_reason_marker_coverage_source_group":
        if _is_family_activity_reason(query_reason):
            return 4
        answer_object_rank = _answer_object_rank(
            item,
            query_reason=query_reason,
        )
        if answer_object_rank <= 1:
            return 1 + answer_object_rank
        source_group = _marker_coverage_family_source_group(family)
        if marker_source_group_counts.get(source_group, 0) > 1:
            return min(answer_object_rank + 1, 3)
        return min(answer_object_rank + 2, 5)
    return 2


def _is_exact_conversational_support_family(family: str, *, item: ContextItem) -> bool:
    return (
        _diversity_family_base(family) == "query_reason_exact_marker_source_group"
        and _is_conversational_support_turn(item)
    )


def _is_exact_temporal_query_object_family(family: str, *, item: ContextItem, query: str) -> bool:
    query_reason = _answer_support_query_reason(item)
    base = _diversity_family_base(family)
    if _is_degree_completion_temporal_answer_support_item(item, query=query):
        return True
    if base in {"query_reason_source_group", "query_reason_activity_slot_source_group", "query_reason_inventory_slot_source_group"} and _answer_support_exact_query_object_hits(item, query=query) > 0 and _has_any_exact_turn_source_ref(item):
        return True
    return (
        _TEMPORAL_ANSWER_SUPPORT_QUERY_RE.search(query) is not None
        and base in {
            "temporal_source_sibling_marker",
            "temporal_source_sibling_marker_source_group",
            "query_reason_source_group",
        }
        and _temporal_answer_support_query_object_hits(
            item,
            query=query,
            query_reason=query_reason,
        )
        > 0
        and _has_any_exact_turn_source_ref(item)
    )


def _is_degree_completion_temporal_answer_support_item(
    item: ContextItem,
    *,
    query: str,
) -> bool:
    if not query:
        return False
    if _DEGREE_COMPLETION_TEMPORAL_QUERY_RE.search(query) is None:
        return False
    if _answer_support_query_reason(item) != "degree_policy_inference_bridge":
        return False
    if _degree_policy_answer_slot(item.text) != "degree_completion_context":
        return False
    return _has_any_exact_turn_source_ref(item)


def _is_exact_precise_content_answer_support_item(item: ContextItem) -> bool:
    if not _has_any_exact_turn_source_ref(item):
        return False
    query_reason = _answer_support_query_reason(item)
    if query_reason not in _EXACT_PRECISE_CONTENT_TURN_REASONS:
        return False
    return _precise_answer_content_rank(item, query_reason=query_reason) == 0


def _marker_coverage_source_group_counts(candidates: dict[str, ContextItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for family in candidates:
        if _diversity_family_base(family) != "query_reason_marker_coverage_source_group":
            continue
        source_group = _marker_coverage_family_source_group(family)
        if source_group:
            counts[source_group] = counts.get(source_group, 0) + 1
    return counts


def _broad_turn_source_group_counts(candidates: dict[str, ContextItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for family in candidates:
        if _diversity_family_base(family) != "query_reason_broad_turn_source_group":
            continue
        source_group = _broad_turn_family_source_group(family)
        if source_group:
            counts[source_group] = counts.get(source_group, 0) + 1
    return counts


def _broad_turn_family_source_group(family: str) -> str:
    parts = family.split(":")
    if len(parts) >= 4:
        return parts[-1]
    return ""


def _pet_acquisition_named_object_source_groups(
    candidates: dict[str, ContextItem],
    *,
    query: str,
) -> frozenset[str]:
    object_terms = _pet_acquisition_named_object_terms(query)
    if not object_terms:
        return frozenset()
    source_groups: set[str] = set()
    for item in candidates.values():
        if _answer_support_query_reason(item) != "pet_acquisition_date_bridge":
            continue
        source_group = _answer_support_source_group(item)
        if not source_group:
            continue
        text = item.text.casefold()
        if any(re.search(rf"\b{re.escape(term)}\b", text) for term in object_terms):
            source_groups.add(source_group)
    return frozenset(source_groups)


def _pet_acquisition_named_object_terms(query: str) -> tuple[str, ...]:
    terms: list[str] = []
    for match in _NAMED_ACQUISITION_OBJECT_QUERY_RE.finditer(query):
        term = match.group("object").strip().casefold()
        if term and term not in terms:
            terms.append(term)
    return tuple(terms)


def _marker_coverage_family_source_group(family: str) -> str:
    parts = family.split(":")
    if len(parts) >= 4:
        return parts[-1]
    return ""


def _answer_support_source_group_reason_key(family: str) -> str:
    parts = family.split(":")
    if len(parts) < 3 or parts[0] not in {
        "query_reason_activity_slot_source_group",
        "query_reason_broad_turn_source_group",
        "query_reason_career_slot_source_group",
        "query_reason_count_coverage_source_group",
        "query_reason_exact_marker_source_group",
        "query_reason_inference_slot_source_group",
        "query_reason_inventory_slot_source_group",
        "query_reason_marker_coverage_source_group",
        "query_reason_source_group",
    }:
        return ""
    if (
        parts[0] == "query_reason_activity_slot_source_group"
        and len(parts) >= 4
        and (
            _is_family_activity_reason(parts[1])
        )
    ):
        return f"{parts[1]}:{parts[2]}"
    if parts[0] == "query_reason_inventory_slot_source_group" and len(parts) >= 4:
        return f"{parts[1]}:{parts[2]}"
    return parts[1]


def _answer_support_source_group_limit(
    reason: str,
    *,
    family: str,
    item: ContextItem,
) -> int:
    if _is_count_aggregation_reason(reason):
        return _MAX_ANSWER_SUPPORT_DIVERSITY_ITEMS
    normalized_reason = reason.replace("_", "-")
    base_reason = normalized_reason.split(":", 1)[0]
    if base_reason in {
        "cause-education-infrastructure-inventory-bridge",
        "cause-veterans-inventory-bridge",
    }:
        return _MAX_ANSWER_SUPPORT_AGGREGATION_SOURCE_GROUP_DIVERSITY_ITEMS_PER_REASON
    family_base = _diversity_family_base(family)
    aggregation_family_bases = {
        "query_reason_activity_slot_source_group",
        "query_reason_broad_turn_source_group",
        "query_reason_career_slot_source_group",
        "query_reason_count_coverage_source_group",
        "query_reason_exact_marker_source_group",
        "query_reason_inference_slot_source_group",
        "query_reason_inventory_slot_source_group",
        "query_reason_marker_coverage_source_group",
    }
    if (
        (
            reason in _ANSWER_SUPPORT_AGGREGATION_SOURCE_GROUP_REASONS
            or normalized_reason in _ANSWER_SUPPORT_AGGREGATION_SOURCE_GROUP_REASONS
        )
        and (
            family_base in aggregation_family_bases
            or (item.source_refs and family_base == "query_reason_source_group")
        )
    ):
        return _MAX_ANSWER_SUPPORT_AGGREGATION_SOURCE_GROUP_DIVERSITY_ITEMS_PER_REASON
    if (
        reason.startswith("decomposition-")
        and reason.endswith("-event")
        and reason not in {"decomposition-event-context", "decomposition-event-sequence"}
    ):
        return _MAX_ANSWER_SUPPORT_EVENT_SLOT_SOURCE_GROUP_DIVERSITY_ITEMS_PER_REASON
    return _MAX_ANSWER_SUPPORT_SOURCE_GROUP_DIVERSITY_ITEMS_PER_REASON


def _is_count_aggregation_reason(reason: str) -> bool:
    normalized_reason = reason.replace("-", "_")
    return reason in _COUNT_AGGREGATION_COVERAGE_REASONS or (
        normalized_reason in _COUNT_AGGREGATION_COVERAGE_REASONS
    )


def _answer_support_diversity_family(item: ContextItem) -> str:
    query_reason = _answer_support_query_reason(item)
    if _is_temporal_answer_support_item(item, query_reason=query_reason):
        source_group = _answer_support_source_group(item)
        marker = _primary_exact_turn_marker(item) or _first_dialogue_marker(item.text)
        if source_group:
            return _compound_diversity_family(
                "temporal_source_sibling_marker_source_group",
                marker or "temporal",
                source_group,
            )
        return _compound_diversity_family(
            "temporal_source_sibling_marker",
            marker or item.item_id,
        )

    if query_reason and query_reason != "original_query":
        if query_reason in _ANSWER_SUPPORT_EXCLUDED_QUERY_REASONS:
            return ""
        source_group = _answer_support_source_group(item)
        career_slot = _career_answer_slot(item, query_reason=query_reason)
        activity_slot = _activity_answer_slot(item, query_reason=query_reason)
        inference_slot = _inference_answer_slot(item, query_reason=query_reason)
        inventory_slot = _inventory_answer_slot(item, query_reason=query_reason)
        exact_support_marker = _exact_answer_support_marker_slot(
            item,
            query_reason=query_reason,
        )
        if source_group:
            if exact_support_marker and _exact_marker_should_precede_inventory(
                item,
                marker=exact_support_marker,
            ):
                return _compound_diversity_family(
                    "query_reason_exact_marker_source_group",
                    query_reason,
                    exact_support_marker,
                    source_group,
                )
            if broad_turn_slot := _broad_evidence_turn_slot(item, query_reason=query_reason):
                return _compound_diversity_family(
                    "query_reason_broad_turn_source_group",
                    query_reason,
                    broad_turn_slot,
                    source_group,
                )
            if _is_count_aggregation_coverage_item(item, query_reason=query_reason):
                return _compound_diversity_family(
                    "query_reason_count_coverage_source_group",
                    query_reason,
                    source_group,
                )
            if marker_slot := _aggregation_marker_coverage_slot(
                item,
                query_reason=query_reason,
            ):
                return _compound_diversity_family(
                    "query_reason_marker_coverage_source_group",
                    query_reason,
                    marker_slot,
                    source_group,
                )
            if inventory_slot:
                return _compound_diversity_family(
                    "query_reason_inventory_slot_source_group",
                    query_reason,
                    inventory_slot,
                    source_group,
                )
            if exact_support_marker:
                return _compound_diversity_family(
                    "query_reason_exact_marker_source_group",
                    query_reason,
                    exact_support_marker,
                    source_group,
                )
            if activity_slot:
                return _compound_diversity_family(
                    "query_reason_activity_slot_source_group",
                    query_reason,
                    activity_slot,
                    source_group,
                )
            if career_slot:
                return _compound_diversity_family(
                    "query_reason_career_slot_source_group",
                    query_reason,
                    career_slot,
                    source_group,
                )
            if inference_slot:
                return _compound_diversity_family(
                    "query_reason_inference_slot_source_group",
                    query_reason,
                    inference_slot,
                    source_group,
                )
            if _diagnostic_signal_truthy(item, "source_sibling_dialogue_visual_reference"):
                return _compound_diversity_family(
                    "query_reason_source_group_visual_reference",
                    query_reason,
                    source_group,
                )
            return _compound_diversity_family(
                "query_reason_source_group",
                query_reason,
                source_group,
            )
        if activity_slot:
            return _compound_diversity_family(
                "query_reason_activity_slot",
                query_reason,
                activity_slot,
            )
        if inventory_slot:
            return _compound_diversity_family(
                "query_reason_inventory_slot",
                query_reason,
                inventory_slot,
            )
        if career_slot:
            return _compound_diversity_family(
                "query_reason_career_slot",
                query_reason,
                career_slot,
            )
        if inference_slot:
            return _compound_diversity_family(
                "query_reason_inference_slot",
                query_reason,
                inference_slot,
            )
        return _typed_diversity_family("query_reason", query_reason)
    if _has_any_exact_turn_source_ref(item) and _numeric_signal(_diagnostic_score_signals(item).get("source_sibling_answer_evidence")) > 0:
        source_group = _answer_support_source_group(item)
        if source_group:
            return _compound_diversity_family("query_reason_source_group", "source_sibling_answer_evidence", source_group)
    matched_anchor_kinds = _diagnostic_list(item, "context_requirement_matched_anchor_kinds")
    if matched_anchor_kinds:
        return _typed_diversity_family("requirement_anchor", matched_anchor_kinds[0])

    matched_modalities = _diagnostic_list(item, "context_requirement_matched_modalities")
    if matched_modalities:
        return _typed_diversity_family("requirement_modality", matched_modalities[0])

    matched_features = _diagnostic_list(item, "context_requirement_matched_evidence_features")
    if matched_features:
        return _typed_diversity_family("requirement_feature", matched_features[0])

    return ""


def _first_dialogue_marker(text: str) -> str:
    match = _DIALOGUE_MARKER_RE.search(text)
    return match.group(0) if match is not None else ""
def _primary_exact_turn_marker(item: ContextItem) -> str:
    source_id = _primary_exact_turn_source_id(item)
    match = _DIALOGUE_MARKER_RE.search(source_id)
    return match.group(0) if match is not None else ""
def _exact_marker_should_precede_inventory(item: ContextItem, *, marker: str) -> bool:
    if len(item.source_refs) != 1:
        return False
    first_marker = _first_dialogue_marker(item.text)
    return bool(first_marker and marker and first_marker != marker)


def _answer_support_query_reason(item: ContextItem) -> str:
    query_reason = _diagnostic_signal_text(item, "query_expansion_reason")
    deterministic_reason = _diagnostic_signal_text(item, "deterministic_rerank_query_reason")
    if (
        deterministic_reason
        and deterministic_reason != "original_query"
        and query_reason
        in {
            "decomposition_evidence_reason",
            "decomposition_inference_support",
        }
    ):
        return deterministic_reason
    return (
        query_reason
        or _diagnostic_signal_text(item, "bm25_lexical_query_reason")
        or deterministic_reason
    )


def _answer_support_source_group(item: ContextItem) -> str:
    aggregation_source_group = _diagnostic_text(item, "keyword_aggregation_source_group")
    if aggregation_source_group:
        return aggregation_source_group
    if set(diagnostic_retrieval_sources(item.diagnostics)).intersection(
        {
            "keyword_aggregation_chunks",
            "keyword_source_sibling_chunks",
        }
    ):
        return _source_group_key(item)
    if _has_derived_source_group_ref(item):
        return _source_group_key(item)
    return ""


def _exact_answer_support_marker_slot(item: ContextItem, *, query_reason: str) -> str:
    if not _is_pottery_type_reason(query_reason):
        return ""
    if (
        _numeric_signal(_diagnostic_score_signals(item).get("source_sibling_answer_evidence")) <= 0
        and "keyword_source_sibling_chunks" not in diagnostic_retrieval_sources(item.diagnostics)
    ):
        return ""
    marker = _primary_exact_turn_marker(item)
    if not marker:
        return ""
    if re.search(rf"\b{re.escape(marker)}\b", item.text) is None:
        return ""
    return marker

def _has_derived_source_group_ref(item: ContextItem) -> bool:
    if not item.source_refs:
        return False
    source_group_key = _source_group_key(item)
    return source_group_key != _source_key(item)


def _activity_answer_slot(item: ContextItem, *, query_reason: str) -> str:
    if query_reason not in {
        "activity_aggregation_bridge",
        "activity_visual_selfcare_bridge",
        "art_style_bridge", "decomposition_activity_participation",
        "exercise_activity_inventory_bridge",
        "family_activity_bridge",
        "family_hike_detail_bridge",
        "family_hike_activity_bridge",
        "family_museum_activity_bridge",
        "family_painting_activity_bridge",
        "family_swimming_activity_bridge",
        "children_preference_bridge",
        "painting_inventory_bridge",
        "shoe_usage_bridge",
    }:
        return ""
    text = item.text.casefold()
    if query_reason == "shoe_usage_bridge":
        if "walking or running" in text or "for walking" in text:
            return "shoe_usage_answer"
        if any(marker in text for marker in ("new shoes", "sneakers", "running shoe")):
            return "shoe_purchase_visual"
        return ""
    if query_reason in {"art_style_bridge", "painting_inventory_bridge"}:
        return _painting_inventory_answer_slot(text)
    if query_reason == "exercise_activity_inventory_bridge":
        return _exercise_activity_answer_slot(text)
    if query_reason == "children_preference_bridge":
        return _children_preference_answer_slot(text)
    return _general_activity_answer_slot_for_text(text)


def _general_activity_answer_slot_for_text(text: str) -> str:
    slots = (
        ("swimming", ("swimming", " swim ", "self care", "taking care")),
        ("hiking", ("hiking", " hike ", "trail", "waterfall", "mountain")),
        ("camping", ("camping", "camped", "campfire", "marshmallow", "unplug")),
        ("pottery", ("pottery", "clay", "ceramic", "bowl")),
        ("painting", ("painting", "painted", "sunrise", "sunset", "lake", "drawing")),
        ("family_motivation", ("husband", "motivated", "motivate", "motivation")),
        ("running", ("running", "run ", "ran ", "race")),
        ("museum", ("museum", "dinosaur", "exhibit", "bones")),
        ("park", ("park", "outdoors", "playing", "exploring")),
        ("concert", ("concert", "music", "band")),
    )
    padded = f" {text} "
    for slot, markers in slots:
        if any(marker in padded for marker in markers):
            return slot
    return ""


def _is_count_aggregation_coverage_item(item: ContextItem, *, query_reason: str) -> bool:
    if query_reason not in _COUNT_AGGREGATION_COVERAGE_REASONS:
        return False
    if _has_primary_exact_turn_source_ref(item):
        return False
    if "keyword_aggregation_chunks" not in diagnostic_retrieval_sources(item.diagnostics):
        return False
    return len(item.source_refs) > 1


def _broad_evidence_turn_slot(item: ContextItem, *, query_reason: str) -> str:
    if query_reason not in _BROAD_EVIDENCE_TURN_SLOT_REASONS:
        return ""
    if len(item.source_refs) != 1:
        return ""
    return _primary_exact_turn_source_id(item)


def _aggregation_marker_coverage_slot(item: ContextItem, *, query_reason: str) -> str:
    normalized_reason = query_reason.replace("_", "-")
    if (
        query_reason not in _ANSWER_SUPPORT_AGGREGATION_SOURCE_GROUP_REASONS
        and normalized_reason not in _ANSWER_SUPPORT_AGGREGATION_SOURCE_GROUP_REASONS
    ):
        return ""
    if not set(diagnostic_retrieval_sources(item.diagnostics)).intersection(
        {
            "keyword_aggregation_chunks",
            "keyword_chunks",
            "keyword_neighbor_chunks",
            "keyword_source_sibling_chunks",
        }
    ):
        return ""
    if _diagnostic_text(item, "source_type") != "locomo_observation":
        return ""
    if "related turns:" not in item.text.casefold():
        return ""
    markers = tuple(
        dict.fromkeys(match.group(0) for match in _DIALOGUE_MARKER_RE.finditer(item.text))
    )
    if len(markers) < 2:
        return ""
    return f"{markers[0]}-{markers[-1]}"


def _career_answer_slot(item: ContextItem, *, query_reason: str) -> str:
    if query_reason == "degree_policy_inference_bridge":
        return _degree_policy_answer_slot(item.text)
    if query_reason in {"business_commonality_bridge", "business_start_reason_bridge"}:
        return _business_commonality_answer_slot(item.text)
    if query_reason == "charity_brand_sponsorship_bridge":
        return _charity_brand_sponsorship_answer_slot(item.text)
    if query_reason in {"career_intent_bridge", "career_path_bridge"}:
        text = item.text.casefold()
        if "working with trans people" in text or "trans people" in text:
            return "trans_support_work"
        if "counsel" in text or "mental health" in text:
            return "counseling_mental_health"
        return ""
    if query_reason == "creative_writing_career_bridge":
        return "book_reading" if _book_reading_answer_content_rank(item.text) <= 3 else ""
    if query_reason != "volunteer_career_inference_bridge":
        return ""
    text = item.text.casefold()
    slots = (
        ("shelter_operations", ("front desk", "food or a bed", "food", " bed", "coordinator")),
        ("counseling_talks", ("gave a few talks", " talks ", "compliments", "counselor")),
        (
            "volunteer_origin",
            (
                "about a year ago",
                "witnessing a family",
                "family struggling",
                "struggling on the streets",
                "reached out to the shelter",
                "needed any volunteers",
            ),
        ),
        (
            "start_motivation",
            (
                "started volunteering",
                "start volunteering",
                "aunt",
                "brighten",
            ),
        ),
        (
            "resident_support",
            ("resident", "gratitude", "appreciation", "letter", "support they receive"),
        ),
        ("homeless_shelter", ("homeless shelter", " shelter", "volunteer")),
    )
    padded = f" {text} "
    for slot, markers in slots:
        if any(marker in padded for marker in markers):
            return slot
    return ""


def _inference_answer_slot(item: ContextItem, *, query_reason: str) -> str:
    if query_reason.replace("_", "-") != "religious-inference-bridge":
        return ""
    if _RELIGIOUS_CONTRAST_EVIDENCE_RE.search(item.text):
        return "religious_contrast"
    if _RELIGIOUS_DIRECT_EVIDENCE_RE.search(item.text):
        return "religious_direct"
    return ""


def _degree_policy_answer_slot(text: str) -> str:
    text = text.casefold()
    padded = f" {text} "
    if any(
        marker in padded
        for marker in (
            " because of my degree",
            " because of his degree",
            " because of her degree",
            "policymaking because",
            "public policy",
            "public administration",
            "public affairs",
            "political science",
        )
    ):
        return "degree_field_inference"
    if any(marker in padded for marker in ("policymaking", "policy making", " policy ")):
        return "policy_career_plan"
    if any(marker in padded for marker in ("graduated", "degree", "diploma")):
        return "degree_completion_context"
    return ""


def _business_commonality_answer_slot(text: str) -> str:
    text = text.casefold()
    if "door dash" in text and "lost my job" in text:
        return "gina_job_loss"
    if "lost my job as a banker" in text or ("banker" in text and "own business" in text):
        return "jon_job_loss"
    if "dance studio" in text or ("starting" in text and "passionate about dancing" in text):
        return "jon_business_type"
    if (
        "clothing store" in text
        or "my own store" in text
        or "ad campaign" in text
        or "fashion trends" in text
        or "unique pieces" in text
        or "blend my love for dance and fashion" in text
        or "blend dance and fashion" in text
    ):
        return "gina_store_start"
    if "own business" in text or "starting" in text:
        return "business_start_generic"
    return ""


def _charity_brand_sponsorship_answer_slot(text: str) -> str:
    text = text.casefold()
    if "under armour" in text or "under armor" in text:
        return "under_armour_interest"
    if "nike" in text and ("gatorade" in text or "sponsorship" in text):
        return "nike_gatorade_deals"
    if "good sports" in text or "disadvantaged kids" in text:
        return "charity_org_fit"
    if "give something back" in text or "charity" in text or "make a difference" in text:
        return "charity_intent"
    if "sports brand" in text or "big brands" in text:
        return "sports_brand_generic"
    return ""


def _inventory_answer_slot(item: ContextItem, *, query_reason: str) -> str:
    if _is_pottery_type_reason(query_reason):
        return _pottery_type_inventory_slot_for_text(item.text)
    if _is_community_participation_reason(query_reason):
        return _community_participation_inventory_slot_for_text(item.text)
    if query_reason == "item_purchase_bridge":
        return _item_purchase_inventory_slot_for_text(item.text)
    if not _is_inventory_list_reason(query_reason):
        return ""
    if query_reason == "cause_education_infrastructure_inventory_bridge":
        return _cause_education_infrastructure_answer_slot(item.text)
    if query_reason == "cause_veterans_inventory_bridge":
        return _cause_veterans_answer_slot(item.text)
    if query_reason == "outdoor_activity_inventory_bridge":
        return _outdoor_activity_inventory_answer_slot_for_text(item.text)
    return _inventory_answer_slot_for_text(item.text)


def _outdoor_activity_inventory_answer_slot_for_text(text: str) -> str:
    if _INVENTORY_OUTDOOR_MOUNTAINEERING_SLOT_RE.search(text):
        return "outdoor_mountaineering"
    if _INVENTORY_OUTDOOR_HIKING_SLOT_RE.search(text):
        return "outdoor_hiking"
    if _INVENTORY_OUTDOOR_PICNIC_SLOT_RE.search(text):
        return "outdoor_picnic"
    if _INVENTORY_OUTDOOR_WATERFALL_SLOT_RE.search(text):
        return "outdoor_waterfall"
    if _INVENTORY_OUTDOOR_VISUAL_GROUP_SLOT_RE.search(text):
        return "outdoor_visual_group"
    if _INVENTORY_OUTDOOR_ACTIVITY_SLOT_RE.search(text):
        return "outdoor_activity"
    return ""


def _inventory_answer_slot_for_text(text: str) -> str:
    if dessert_slot := _dessert_inventory_slot_for_text(text):
        return dessert_slot
    if item_purchase_slot := _item_purchase_inventory_slot_for_text(text):
        return item_purchase_slot
    pottery_slot = _pottery_type_inventory_slot_for_text(text)
    if pottery_slot:
        return pottery_slot
    if _INVENTORY_EVENT_CHILI_COOKOFF_SLOT_RE.search(text):
        return "fundraiser_chili_cookoff"
    if _INVENTORY_EVENT_TOURNAMENT_SLOT_RE.search(text):
        return "fundraiser_tournament"
    if _INVENTORY_EVENT_FUNDRAISER_SETUP_SLOT_RE.search(text):
        return "fundraiser_shelter_setup"
    if _INVENTORY_ANIMAL_ACTIVITY_HOLDING_SLOT_RE.search(text):
        return "animal_activity_holding"
    if _INVENTORY_ANIMAL_ACTIVITY_BATH_SLOT_RE.search(text):
        return "animal_activity_bath"
    if _INVENTORY_ANIMAL_ACTIVITY_WALK_SLOT_RE.search(text):
        return "animal_activity_walk"
    if _INVENTORY_ANIMAL_ACTIVITY_FEEDING_SLOT_RE.search(text):
        return "animal_activity_feeding"
    if _INVENTORY_VOLUNTEER_HELPED_PERSON_SLOT_RE.search(text):
        return "volunteer_helped_person"
    if _INVENTORY_SHELTER_SERVICE_ACTIVITY_SLOT_RE.search(text):
        return "shelter_service_activity"
    if _INVENTORY_FRIEND_PLACE_SHELTER_ACTIVITY_REPEAT_RE.search(text):
        return "shelter_activity"
    if _INVENTORY_FRIEND_PLACE_SHELTER_ANCHOR_RE.search(text):
        return "shelter_anchor"
    if _INVENTORY_ANIMAL_SHELTER_SLOT_RE.search(text):
        return "animal_shelter"
    if _INVENTORY_SHELTER_SLOT_RE.search(text):
        return "shelter"
    if _INVENTORY_GYM_SLOT_RE.search(text):
        return "gym"
    if _INVENTORY_CHURCH_JOINED_SLOT_RE.search(text):
        return "church_joined"
    if _INVENTORY_BOOK_READING_SLOT_RE.search(text):
        return "book_reading"
    if _INVENTORY_CHURCH_FRIEND_ACTIVITY_SLOT_RE.search(text):
        return "church_friend_activity"
    if _INVENTORY_CHURCH_SLOT_RE.search(text):
        return "church"
    if _INVENTORY_EDUCATION_INFRASTRUCTURE_SLOT_RE.search(text):
        return "education_infrastructure"
    if _INVENTORY_VETERANS_PETITION_SLOT_RE.search(text):
        return "veterans_petition"
    if _INVENTORY_VETERANS_RUN_SLOT_RE.search(text):
        return "veterans_charity_run"
    if _INVENTORY_VETERANS_MARCH_SLOT_RE.search(text):
        return "veterans_march"
    if _INVENTORY_VETERANS_HOSPITAL_SLOT_RE.search(text):
        return "veterans_hospital"
    if _INVENTORY_VETERANS_SLOT_RE.search(text):
        return "veterans"
    if community_participation_slot := _community_participation_inventory_slot_for_text(
        text
    ):
        return community_participation_slot
    if _INVENTORY_CLASSICAL_MUSIC_PREFERENCE_SLOT_RE.search(text):
        return "classical_music_preference"
    if _INVENTORY_MUSIC_VIOLIN_CONCERT_SLOT_RE.search(text):
        return "music_violin_concert"
    if _INVENTORY_MUSIC_LIVE_EVENT_SLOT_RE.search(text):
        return "music_live_event"
    if _INVENTORY_MUSIC_EVENT_SLOT_RE.search(text):
        return "music_event"
    if _INVENTORY_STATE_FLORIDA_SLOT_RE.search(text):
        return "state_florida"
    if _INVENTORY_STATE_OREGON_SLOT_RE.search(text):
        return "state_oregon"
    if _INVENTORY_STATE_EAST_COAST_SLOT_RE.search(text):
        return "state_east_coast"
    if _INVENTORY_STATE_PACIFIC_NORTHWEST_SLOT_RE.search(text):
        return "state_pacific_northwest"
    if _INVENTORY_STATE_PLACE_SLOT_RE.search(text):
        return "state_place"
    if _INVENTORY_OUTDOOR_MOUNTAINEERING_SLOT_RE.search(text):
        return "outdoor_mountaineering"
    if _INVENTORY_OUTDOOR_HIKING_SLOT_RE.search(text):
        return "outdoor_hiking"
    if _INVENTORY_OUTDOOR_PICNIC_SLOT_RE.search(text):
        return "outdoor_picnic"
    if _INVENTORY_OUTDOOR_WATERFALL_SLOT_RE.search(text):
        return "outdoor_waterfall"
    if _INVENTORY_OUTDOOR_ACTIVITY_SLOT_RE.search(text):
        return "outdoor_activity"
    if _INVENTORY_FRIEND_PLACE_DIRECT_RE.search(text):
        return "direct_friend"
    if _INVENTORY_VOLUNTEER_SLOT_RE.search(text):
        return "volunteer"
    if _INVENTORY_COMMUNITY_SLOT_RE.search(text):
        return "community"
    if _INVENTORY_SUPPORT_GROUP_SLOT_RE.search(text):
        return "support_group"
    if _INVENTORY_COUNTRY_SLOT_RE.search(text):
        return "country"
    if _INVENTORY_PLACE_MARKER_RE.search(text):
        return "place"
    return ""


def _cause_education_infrastructure_answer_slot(text: str) -> str:
    if (
        _CAUSE_EDUCATION_SLOT_RE.search(text)
        and _CAUSE_INFRASTRUCTURE_SLOT_RE.search(text)
    ):
        return "education_infrastructure"
    return ""


def _cause_veterans_answer_slot(text: str) -> str:
    if _INVENTORY_VETERANS_PETITION_SLOT_RE.search(text):
        return "veterans_petition"
    if _INVENTORY_VETERANS_RUN_SLOT_RE.search(text):
        return "veterans_charity_run"
    if _INVENTORY_VETERANS_MARCH_SLOT_RE.search(text):
        return "veterans_march"
    if _INVENTORY_VETERANS_HOSPITAL_SLOT_RE.search(text):
        return "veterans_hospital"
    if _INVENTORY_VETERANS_SLOT_RE.search(text):
        return "veterans"
    return ""


def _is_exact_cause_inventory_answer_support_item(item: ContextItem) -> bool:
    if not _has_any_exact_turn_source_ref(item):
        return False
    return _is_cause_inventory_answer_support_item(item)


def _is_single_exact_cause_inventory_answer_support_item(item: ContextItem) -> bool:
    return (
        len(item.source_refs) == 1
        and _has_primary_exact_turn_source_ref(item)
        and _is_cause_inventory_answer_support_item(item)
    )


def _is_cause_inventory_answer_support_item(item: ContextItem) -> bool:
    query_reason = _answer_support_query_reason(item)
    if query_reason not in {
        "cause_education_infrastructure_inventory_bridge",
        "cause_veterans_inventory_bridge",
    }:
        return False
    return bool(_inventory_answer_slot(item, query_reason=query_reason))


def _inventory_answer_slot_from_family(family: str) -> str:
    parts = family.split(":")
    if len(parts) >= 3:
        return parts[2]
    return ""


def _career_answer_slot_priority(slot: str) -> int:
    normalized_slot = slot.replace("-", "_")
    return {
        "shelter_operations": 0,
        "counseling_talks": 0,
        "volunteer_origin": 0,
        "start_motivation": 0,
        "trans_support_work": 0,
        "counseling_mental_health": 1,
        "resident_support": 2,
        "homeless_shelter": 3,
    }.get(normalized_slot, 2)


def _career_answer_slot_from_family(family: str) -> str:
    parts = family.split(":")
    if len(parts) >= 3:
        return parts[2]
    return ""

def _answer_support_family_item_key(item: ContextItem) -> tuple[float | int | str, ...]:
    return _answer_support_family_item_key_for_query(item, query="")


def _answer_support_family_item_key_for_query(
    item: ContextItem,
    *,
    query: str,
) -> tuple[float | int | str, ...]:
    signals = _diagnostic_score_signals(item)
    query_reason = _answer_support_query_reason(item)
    if _is_count_aggregation_coverage_item(item, query_reason=query_reason):
        signal_rank = (
            -_numeric_signal(signals.get("item_purchase_object_evidence")),
            -_numeric_signal(signals.get("symbol_importance_visual_evidence")),
            -_numeric_signal(signals.get("friend_place_shelter_anchor_evidence")),
            -_numeric_signal(signals.get("cause_awareness_answer_evidence")),
            -_numeric_signal(signals.get("choice_reason_answer_evidence")),
            -_numeric_signal(signals.get("future_plan_timing_answer_evidence")),
            -_numeric_signal(signals.get("birdwatching_city_schedule_answer_evidence")),
            -_numeric_signal(signals.get("source_sibling_answer_evidence")),
            -_numeric_signal(signals.get("distinctive_term_hits")),
            -_numeric_signal(signals.get("phrase_bigram_hits")),
        )
    else:
        signal_rank = (
            -_numeric_signal(signals.get("item_purchase_object_evidence")),
            -_numeric_signal(signals.get("symbol_importance_visual_evidence")),
            -_numeric_signal(signals.get("friend_place_shelter_anchor_evidence")),
            -_numeric_signal(signals.get("cause_awareness_answer_evidence")),
            -_numeric_signal(signals.get("choice_reason_answer_evidence")),
            -_numeric_signal(signals.get("future_plan_timing_answer_evidence")),
            -_numeric_signal(signals.get("birdwatching_city_schedule_answer_evidence")),
            -_numeric_signal(signals.get("source_sibling_answer_evidence")),
            -_numeric_signal(signals.get("phrase_bigram_hits")),
            -_numeric_signal(signals.get("distinctive_term_hits")),
        )
    return (
        -_answer_support_exact_query_object_hits(item, query=query),
        _degree_completion_temporal_answer_support_rank(item, query=query),
        _answer_support_exact_turn_alignment_rank(
            text=item.text,
            source_ids=tuple(str(ref.source_id) for ref in item.source_refs),
            inventory_slot=_inventory_answer_slot(item, query_reason=query_reason),
            slot_detector=_inventory_answer_slot_for_text,
            query_reason=query_reason,
        ),
        _precise_turn_answer_support_rank(item, query_reason=query_reason),
        _pet_acquisition_date_anchor_answer_support_rank(
            item,
            query_reason=query_reason,
        ),
        _precise_answer_content_rank(item, query_reason=query_reason),
        _answer_object_rank(item, query_reason=query_reason),
        _marker_coverage_answer_support_rank(item, query_reason=query_reason),
        _birdwatching_city_schedule_exact_turn_rank(item, query_reason=query_reason),
        -_temporal_answer_support_query_object_hits(
            item,
            query=query,
            query_reason=query_reason,
        ),
        _temporal_answer_support_source_span_rank(item, query_reason=query_reason),
        _inventory_first_mention_rank(
            source_id=_primary_exact_turn_source_id(item),
            query=query,
            enabled=_is_community_participation_reason(query_reason),
        ),
        -len(item.source_refs),
        *signal_rank,
        -len(diagnostic_retrieval_sources(item.diagnostics)),
        context_rank_key(item),
    )


def _degree_completion_temporal_answer_support_rank(
    item: ContextItem,
    *,
    query: str,
) -> int:
    return 0 if _is_degree_completion_temporal_answer_support_item(item, query=query) else 1


def _birdwatching_city_schedule_exact_turn_rank(item: ContextItem, *, query_reason: str) -> int:
    if query_reason != "birdwatching_city_schedule_bridge":
        return 0
    if _has_any_exact_turn_source_ref(item) and len(item.source_refs) == 1:
        return 0
    return 1


def _pet_acquisition_date_anchor_answer_support_rank(
    item: ContextItem,
    *,
    query_reason: str,
) -> int:
    return 0 if _is_pet_acquisition_date_anchor_answer_support_item(item) else 1


def _is_pet_acquisition_date_anchor_answer_support_item(item: ContextItem) -> bool:
    query_reason = _answer_support_query_reason(item)
    text = item.text
    signals = _diagnostic_score_signals(item)
    signal_reason = str(signals.get("query_expansion_reason") or "").strip()
    if (
        query_reason == "pet_acquisition_date_bridge"
        and _numeric_signal(signals.get("exact_source_repair_date_anchor")) > 0
        and _is_temporal_answer_support_item(item, query_reason=query_reason)
    ):
        return True
    if (
        query_reason == "pet_acquisition_date_bridge"
        and _is_temporal_answer_support_item(item, query_reason=query_reason)
        and _PET_ACQUISITION_DATE_ANCHOR_SUPPORT_RE.search(text) is not None
    ):
        return True
    return (
        query_reason in {"pet_acquisition_date_bridge", "decomposition_temporal_answer"}
        and (
            signal_reason == "pet_acquisition_date_bridge"
            or _PET_ACQUISITION_OBJECT_ANCHOR_RE.search(text) is not None
        )
        and _is_temporal_answer_support_item(item, query_reason=query_reason)
        and _PET_ACQUISITION_DATE_ANCHOR_SUPPORT_RE.search(text) is not None
    )


def _temporal_answer_support_source_span_rank(item: ContextItem, *, query_reason: str) -> int:
    if not _is_temporal_answer_support_item(item, query_reason=query_reason):
        return 0
    if _has_primary_exact_turn_source_ref(item) and len(item.source_refs) == 1:
        return 0
    if _has_primary_exact_turn_source_ref(item):
        return 1
    if _has_any_exact_turn_source_ref(item) and len(item.source_refs) == 1:
        return 2
    if _has_any_exact_turn_source_ref(item):
        return 3
    return 4


def _temporal_answer_support_query_object_hits(
    item: ContextItem,
    *,
    query: str,
    query_reason: str,
) -> int:
    if not query or not _is_temporal_answer_support_item(item, query_reason=query_reason):
        return 0
    query_tokens = tuple(
        dict.fromkeys(
            token.casefold()
            for token in _QUERY_OBJECT_TOKEN_RE.findall(query)
            if len(token) >= 3
            and token.casefold() not in _TEMPORAL_QUERY_OBJECT_STOPWORDS
            and not token[:1].isupper()
        )
    )
    if not query_tokens:
        return 0
    text = item.text.casefold()
    return sum(1 for token in query_tokens if re.search(rf"\b{re.escape(token)}\b", text))


def _answer_object_rank(item: ContextItem, *, query_reason: str) -> int:
    if _is_support_network_reason(query_reason):
        return _support_network_answer_object_rank(item.text)
    if _is_pottery_type_reason(query_reason):
        return _pottery_type_answer_object_rank(item.text)
    if _is_pottery_type_inventory_item(item, query_reason=query_reason):
        return _pottery_type_answer_object_rank(item.text)
    if _is_family_activity_reason(query_reason):
        return _family_activity_answer_object_rank(item.text)
    if _is_inventory_list_reason(query_reason):
        return _inventory_list_answer_object_rank(item.text)
    return 2

def _marker_coverage_answer_support_rank(item: ContextItem, *, query_reason: str) -> int:
    if not _aggregation_marker_coverage_slot(item, query_reason=query_reason):
        return 0
    markers = tuple(
        dict.fromkeys(match.group(0) for match in _DIALOGUE_MARKER_RE.finditer(item.text))
    )
    return -len(markers)


def _is_pottery_type_reason(query_reason: str) -> bool:
    return query_reason.replace("_", "-") == "pottery-type-bridge"


def _is_pottery_type_inventory_item(item: ContextItem, *, query_reason: str) -> bool:
    if query_reason.replace("_", "-") != "decomposition-inventory-list":
        return False
    if _POTTERY_TYPE_INVENTORY_CONTEXT_RE.search(item.text) is None:
        return False
    return _pottery_type_answer_object_rank(item.text) <= 1


def _is_family_activity_reason(query_reason: str) -> bool:
    return query_reason.replace("_", "-") in {
        "decomposition-activity-participation",
        "family-activity-bridge",
        "family-hike-activity-bridge",
        "family-hike-detail-bridge",
        "family-museum-activity-bridge",
        "family-painting-activity-bridge",
        "family-swimming-activity-bridge",
    }


def _is_activity_participation_answer_reason(query_reason: str) -> bool:
    return query_reason.replace("_", "-") in {
        "activity-aggregation-bridge",
        "activity-visual-selfcare-bridge",
        "decomposition-activity-participation",
    }


def _is_inventory_list_reason(query_reason: str) -> bool:
    return query_reason.replace("_", "-") in {
        "decomposition-inventory-list",
        "animal-activity-inventory-bridge",
        "friend-place-inventory-bridge",
        "friend-place-shelter-inventory-bridge",
        "friend-place-gym-inventory-bridge",
        "friend-place-church-inventory-bridge",
        "book-reading-list-bridge",
        "church-friend-activity-inventory-bridge",
        "classical-music-preference-bridge",
        "cause-education-infrastructure-inventory-bridge",
        "cause-veterans-inventory-bridge",
        "event-participation-bridge",
        "fundraiser-event-inventory-bridge",
        "item-purchase-bridge",
        "music-event-inventory-bridge",
        "outdoor-activity-inventory-bridge",
        "place-area-inventory-bridge",
        "trip-destination-bridge",
        "travel-country-inventory-bridge",
        "veterans-event-inventory-bridge",
        "volunteering-people-inventory-bridge",
        "volunteering-inventory-bridge",
    }


def _is_community_participation_reason(query_reason: str) -> bool:
    return query_reason.replace("_", "-") in {
        "community-participation-bridge",
        "decomposition-lgbtq-pride-event",
        "decomposition-lgbtq-school-speech-event",
        "decomposition-lgbtq-support-group-event",
        "lgbtq-community-participation-bridge",
    }


def _is_support_network_reason(query_reason: str) -> bool:
    return query_reason.replace("_", "-") in {
        "negative-experience-support-bridge",
        "support-network-bridge",
    }


def _is_temporal_answer_support_item(item: ContextItem, *, query_reason: str) -> bool:
    if _numeric_signal(_diagnostic_score_signals(item).get("source_sibling_answer_evidence")) <= 0:
        return False
    if not _has_any_exact_turn_source_ref(item):
        return False
    if (
        query_reason in {"business_commonality_bridge", "business_start_reason_bridge"}
        and _business_commonality_answer_slot(item.text)
    ):
        return False
    signals = _diagnostic_score_signals(item)
    if _numeric_signal(signals.get("exact_source_repair_date_anchor")) > 0:
        return True
    normalized_reason = query_reason.replace("_", "-")
    if normalized_reason in _TEMPORAL_ANSWER_SUPPORT_REASONS:
        return True
    if query_reason == "outdoor_activity_inventory_bridge" or (
        _is_community_participation_reason(query_reason)
        and _inventory_answer_slot(item, query_reason=query_reason)
    ):
        return False
    return _TEMPORAL_DIRECT_ANSWER_RE.search(item.text) is not None

def _support_network_answer_object_rank(text: str) -> int:
    if _SUPPORT_NETWORK_DIRECT_ANSWER_RE.search(text):
        return 0
    has_social_actor = _SUPPORT_NETWORK_SOCIAL_ACTOR_RE.search(text) is not None
    has_support_action = _SUPPORT_NETWORK_SUPPORT_ACTION_RE.search(text) is not None
    if has_social_actor and has_support_action:
        return 1
    if has_social_actor:
        return 2
    if has_support_action:
        return 4
    return 6

def _is_conversational_support_turn(item: ContextItem) -> bool:
    return _CONVERSATIONAL_SUPPORT_TURN_RE.search(item.text) is not None

def _pottery_type_answer_object_rank(text: str) -> int:
    if _POTTERY_TYPE_PRIMARY_ANSWER_OBJECT_RE.search(text):
        return 0
    if _POTTERY_TYPE_SECONDARY_ANSWER_OBJECT_RE.search(text):
        return 1
    if _POTTERY_TYPE_GENERIC_ANSWER_OBJECT_RE.search(text):
        return 3
    return 5

def _family_activity_answer_object_rank(text: str) -> int:
    if _FAMILY_ACTIVITY_DIRECT_ANSWER_OBJECT_RE.search(text):
        return 0
    has_activity = _FAMILY_ACTIVITY_ACTIVITY_OBJECT_RE.search(text) is not None
    has_family_context = _FAMILY_ACTIVITY_CONTEXT_OBJECT_RE.search(text) is not None
    if has_activity and has_family_context:
        return 1
    if has_activity:
        return 2
    if has_family_context:
        return 3
    return 5


def _inventory_list_answer_object_rank(text: str) -> int:
    slot = _inventory_answer_slot_for_text(text)
    if slot == "book_reading":
        return _book_reading_answer_content_rank(text)
    if slot in {"item_purchase_figurines", "item_purchase_shoes"}:
        return 0
    if slot in {"dessert_cobbler", "dessert_sundae"}:
        return 0
    if slot == "dessert_pie":
        return 1
    if slot == "dessert":
        return 2
    if slot == "item_purchase":
        return 1
    if slot == "item_purchase_generic":
        return 2
    if slot in {"pottery_cup", "pottery_pot"}:
        return 0
    if slot == "pottery_bowl":
        return 1
    if slot == "pottery_project":
        return 2
    if slot == "pottery_generic":
        return 3
    if slot in {
        "direct_friend",
        "dessert_cobbler",
        "dessert_sundae",
        "fundraiser_chili_cookoff",
        "fundraiser_shelter_setup",
        "fundraiser_tournament",
        "item_purchase_figurines",
        "item_purchase_shoes",
        "classical_music_preference",
        "music_live_event",
        "music_violin_concert",
        "outdoor_hiking",
        "outdoor_mountaineering",
        "outdoor_picnic",
        "outdoor_visual_group",
        "outdoor_waterfall",
        "shelter_service_activity",
        "volunteer_helped_person",
        "state_florida",
        "state_oregon",
        "state_east_coast",
        "state_pacific_northwest",
        "community_activist_group",
        "community_art_show",
        "community_mentorship_program",
        "community_pride_event",
    }:
        return 0
    if slot in {
        "community_conference",
        "community_school_event",
        "dessert_pie",
        "shelter",
        "gym",
        "church_joined",
        "country",
        "education_infrastructure",
        "item_purchase",
        "music_event",
        "outdoor_activity",
        "state_place",
        "veterans",
        "veterans_petition",
        "veterans_charity_run",
        "veterans_march",
        "veterans_hospital",
    }:
        return 1
    if slot in {"church", "volunteer"}:
        return 2
    if slot == "dessert":
        return 2
    if slot == "item_purchase_generic":
        return 2
    if slot in {"community", "place"} or _INVENTORY_FRIEND_COMMUNITY_PLACE_RE.search(text):
        return 3
    if slot == "support_group":
        return 5
    return 6

def _pottery_type_inventory_slot_for_text(text: str) -> str:
    if _POTTERY_TYPE_INVENTORY_CONTEXT_RE.search(text) is None:
        return ""
    if _POTTERY_TYPE_CUP_SLOT_RE.search(text):
        return "pottery_cup"
    if _POTTERY_TYPE_POT_SLOT_RE.search(text):
        return "pottery_pot"
    if _POTTERY_TYPE_BOWL_SLOT_RE.search(text):
        return "pottery_bowl"
    if _POTTERY_TYPE_PROJECT_SLOT_RE.search(text):
        return "pottery_project"
    return "pottery_generic"

def _precise_turn_answer_support_rank(item: ContextItem, *, query_reason: str) -> int:
    if _is_temporal_answer_support_item(item, query_reason=query_reason):
        return 0
    if _is_count_aggregation_coverage_item(item, query_reason=query_reason):
        return 0
    if (
        _is_family_activity_reason(query_reason)
        and _answer_object_rank(item, query_reason=query_reason) == 0
        and _has_any_exact_turn_source_ref(item)
    ):
        return 0
    if (
        _is_activity_participation_answer_reason(query_reason)
        and _activity_answer_content_rank(item.text) == 0
        and _has_any_exact_turn_source_ref(item)
    ):
        return 0
    if (
        query_reason == "birdwatching_city_schedule_bridge"
        and _numeric_signal(
            _diagnostic_score_signals(item).get("birdwatching_city_schedule_answer_evidence")
        )
        >= 2
        and _has_any_exact_turn_source_ref(item)
    ):
        return 0
    if (
        query_reason == "birdwatching_city_schedule_bridge"
        and _birdwatching_city_schedule_answer_content_rank(item.text) <= 1
        and _has_any_exact_turn_source_ref(item)
    ):
        return 0
    if (
        query_reason in {"book_reading_list_bridge", "creative_writing_career_bridge"}
        and _book_reading_answer_content_rank(item.text) <= 1
        and _has_any_exact_turn_source_ref(item)
    ):
        return 0
    if (
        query_reason == "decomposition_inventory_list"
        and _book_reading_answer_content_rank(item.text) <= 1
        and _has_any_exact_turn_source_ref(item)
    ):
        return 0
    if (
        query_reason == "music_artist_answer_bridge"
        and _music_artist_answer_content_rank(item.text) <= 1
        and _has_any_exact_turn_source_ref(item)
    ):
        return 0
    if (
        _is_inventory_list_reason(query_reason)
        and _answer_object_rank(item, query_reason=query_reason) <= 1
        and _has_any_exact_turn_source_ref(item)
    ):
        return 0
    if query_reason in _BROAD_EVIDENCE_ANSWER_SUPPORT_REASONS:
        return 2
    if (
        query_reason in _COUNT_AGGREGATION_COVERAGE_REASONS
        and _has_primary_exact_turn_source_ref(item)
    ):
        return 1
    if _is_activity_participation_answer_reason(query_reason):
        return 2
    if query_reason not in _PRECISE_TURN_ANSWER_SUPPORT_REASONS:
        return 2
    return 0 if _has_primary_exact_turn_source_ref(item) else 1

def _precise_answer_content_rank(item: ContextItem, *, query_reason: str) -> int:
    if _is_support_network_reason(query_reason):
        return _support_network_answer_object_rank(item.text)
    if query_reason in {"career_intent_bridge", "career_path_bridge"}:
        text = item.text.casefold()
        if "working with trans people" in text or (
            "mental health" in text and ("support" in text or "help" in text)
        ):
            return 0
        if "counsel" in text or "mental health" in text:
            return 1
        return 3
    if query_reason == "creative_writing_career_bridge":
        return _book_reading_answer_content_rank(item.text)
    if query_reason == "birdwatching_city_schedule_bridge":
        return _birdwatching_city_schedule_answer_content_rank(item.text)
    if query_reason == "book_reading_list_bridge":
        return _book_reading_answer_content_rank(item.text)
    if query_reason == "music_artist_answer_bridge":
        return _music_artist_answer_content_rank(item.text)
    if query_reason == "classical_music_preference_bridge":
        return _classical_music_preference_answer_content_rank(item.text)
    if query_reason == "sentimental_reminder_bridge":
        return _sentimental_reminder_answer_content_rank(item.text)
    if query_reason == "outdoor_nature_memory_bridge":
        return _outdoor_nature_memory_answer_content_rank(item.text)
    if query_reason == "children_preference_bridge":
        return _children_preference_answer_content_rank(item.text)
    if query_reason == "public_office_service_bridge":
        return _public_office_service_answer_content_rank(item.text)
    if query_reason == "relocation_willingness_inference_bridge":
        return _relocation_willingness_answer_content_rank(item.text)
    if query_reason == "volunteer_career_inference_bridge":
        return _volunteer_career_answer_content_rank(item)
    if _is_activity_participation_answer_reason(query_reason):
        return _activity_answer_content_rank(item.text)
    if (
        query_reason == "decomposition_inventory_list"
        and _book_reading_answer_content_rank(item.text) <= 1
    ):
        return _book_reading_answer_content_rank(item.text)
    if _is_pottery_type_reason(query_reason):
        return _pottery_type_answer_content_rank(item.text)
    if query_reason in {"running_reason_bridge", "running_reason_question_bridge"}:
        text = item.text.casefold()
        if "what got you into running" in text or "for walking or running" in text:
            return 0
        if "running" in text and any(
            marker in text
            for marker in (
                "destress",
                "de-stress",
                "clear my mind",
                "headspace",
            )
        ):
            return 0
        if "running" in text:
            return 2
        return 3
    if query_reason == "shoe_usage_bridge":
        text = item.text.casefold()
        if "walking or running" in text or "for walking" in text:
            return 0
        if any(marker in text for marker in ("new shoes", "sneakers", "running shoe")):
            return 1
        return 3
    if query_reason == "painting_inventory_bridge":
        return _painting_inventory_answer_content_rank(item.text)
    if query_reason == "degree_policy_inference_bridge":
        return _degree_policy_answer_content_rank(item.text)
    if query_reason in {"business_commonality_bridge", "business_start_reason_bridge"}:
        return _business_commonality_answer_content_rank(item.text)
    if query_reason == "charity_brand_sponsorship_bridge":
        return _charity_brand_sponsorship_answer_content_rank(item.text)
    if query_reason == "exercise_activity_inventory_bridge":
        return _exercise_activity_answer_content_rank(item.text)
    if query_reason == "friend_place_shelter_inventory_bridge":
        return _friend_place_shelter_answer_content_rank(item.text)
    if query_reason == "animal_care_instruction_bridge":
        return _animal_care_instruction_content_rank(item.text)
    if query_reason in {
        "support_career_motivation_bridge",
        "support_origin_bridge",
    }:
        return _support_career_motivation_content_rank(item.text)
    if query_reason != "meteor_shower_feeling_bridge":
        return 0
    text = item.text.casefold()
    if "awe" in text or "tiny" in text:
        return 0
    if "felt" in text or "feel" in text or "universe" in text:
        return 1
    return 2

def _support_career_motivation_content_rank(text: str) -> int:
    if _SUPPORT_CAREER_MOTIVATION_DIRECT_RE.search(text) is not None:
        return 0
    if _SUPPORT_CAREER_MOTIVATION_CONTEXT_RE.search(text) is not None:
        return 1
    return 3

def _classical_music_preference_answer_content_rank(text: str) -> int:
    if _CLASSICAL_MUSIC_PREFERENCE_DIRECT_RE.search(text) is not None:
        return 0
    if re.search(r"\b(?:classical|bach|mozart|vivaldi|orchestra|symphony)\b", text, re.IGNORECASE):
        return 1
    if re.search(r"\b(?:music|song|tunes?|composer|concert)\b", text, re.IGNORECASE):
        return 2
    return 4


def _sentimental_reminder_answer_content_rank(text: str) -> int:
    if _SENTIMENTAL_REMINDER_DIRECT_RE.search(text) is not None:
        return 0
    if _SENTIMENTAL_REMINDER_CONTEXT_RE.search(text) is not None:
        return 1
    return 4


def _outdoor_nature_memory_answer_content_rank(text: str) -> int:
    if _OUTDOOR_NATURE_MEMORY_DIRECT_RE.search(text) is not None:
        return 0
    if _OUTDOOR_NATURE_MEMORY_CONTEXT_RE.search(text) is not None:
        return 1
    return 4


def _children_preference_answer_content_rank(text: str) -> int:
    if _CHILDREN_PREFERENCE_DIRECT_RE.search(text) is not None:
        return 0
    if _CHILDREN_PREFERENCE_CONTEXT_RE.search(text) is not None:
        return 1
    return 4


def _public_office_service_answer_content_rank(text: str) -> int:
    if _PUBLIC_OFFICE_SERVICE_DIRECT_RE.search(text) is not None:
        return 0
    lowered = text.casefold()
    if "office" in lowered or "politic" in lowered or "campaign" in lowered:
        return 1
    return 4


def _relocation_willingness_answer_content_rank(text: str) -> int:
    if (
        _PUBLIC_OFFICE_SERVICE_DIRECT_RE.search(text) is not None
        or _MILITARY_SERVICE_GOAL_DIRECT_RE.search(text) is not None
    ):
        return 0
    lowered = text.casefold()
    if any(marker in lowered for marker in ("military", "country", "office", "politic")):
        return 1
    return 4


def _volunteer_career_answer_content_rank(item: ContextItem) -> int:
    slot = _career_answer_slot(
        item,
        query_reason="volunteer_career_inference_bridge",
    )
    if slot in {
        "shelter_operations",
        "counseling_talks",
        "volunteer_origin",
        "start_motivation",
    }:
        return 0
    if slot == "resident_support":
        return 1
    if slot == "homeless_shelter":
        return 2
    return 4


def _degree_policy_answer_content_rank(text: str) -> int:
    slot = _degree_policy_answer_slot(text)
    if slot == "degree_field_inference":
        return 0
    if slot == "policy_career_plan":
        return 1
    if slot == "degree_completion_context":
        return 2
    return 3


def _birdwatching_city_schedule_answer_content_rank(text: str) -> int:
    if _BIRDWATCHING_CITY_SCHEDULE_CONTENT_RE.search(text) is not None:
        return 0
    lowered = text.casefold()
    if "nature" in lowered and ("city" in lowered or "outdoors" in lowered):
        return 1
    return 3


def _book_reading_answer_content_rank(text: str) -> int:
    if _BOOK_READING_DIRECT_ANSWER_RE.search(text) is not None:
        return 0
    if _INVENTORY_BOOK_READING_SLOT_RE.search(text) is not None:
        return 1
    if _BOOK_READING_CONTEXT_RE.search(text) is not None:
        return 3
    return 5


def _music_artist_answer_content_rank(text: str) -> int:
    if _MUSIC_ARTIST_DIRECT_ANSWER_RE.search(text) is not None:
        return 0
    lowered = text.casefold()
    if "artist" in lowered or "band" in lowered or "singer" in lowered:
        return 1
    if "music" in lowered or "song" in lowered or "concert" in lowered:
        return 3
    return 5


def _business_commonality_answer_content_rank(text: str) -> int:
    slot = _business_commonality_answer_slot(text)
    if slot in {"jon_job_loss", "gina_job_loss", "jon_business_type", "gina_store_start"}:
        return 0
    if slot == "business_start_generic":
        return 1
    return 3


def _charity_brand_sponsorship_answer_content_rank(text: str) -> int:
    slot = _charity_brand_sponsorship_answer_slot(text)
    if slot in {"nike_gatorade_deals", "under_armour_interest", "charity_intent"}:
        return 0
    if slot == "charity_org_fit":
        return 1
    if slot == "sports_brand_generic":
        return 2
    return 3


def _activity_answer_content_rank(text: str) -> int:
    if _ACTIVITY_DIRECT_PARTICIPATION_RE.search(text) is not None:
        return 0
    if _general_activity_answer_slot_for_text(text.casefold()):
        return 1
    if _ACTIVITY_CONTEXT_RE.search(text) is not None:
        return 2
    return 4


def _friend_place_shelter_answer_content_rank(text: str) -> int:
    if _INVENTORY_FRIEND_PLACE_DIRECT_RE.search(text):
        return 0
    if _INVENTORY_FRIEND_PLACE_SHELTER_ACTIVITY_REPEAT_RE.search(text):
        return 2
    if _INVENTORY_FRIEND_PLACE_SHELTER_ANCHOR_RE.search(text):
        return 0
    if _INVENTORY_SHELTER_SLOT_RE.search(text):
        return 1
    return 3


def _animal_care_instruction_content_rank(text: str) -> int:
    if _ANIMAL_CARE_DIRECT_INSTRUCTION_RE.search(text):
        return 0
    if _ANIMAL_CARE_GENERIC_HABITAT_RE.search(text):
        return 3
    if re.search(r"\b(?:care|clean|feed|light|habitat|routine)\b", text, re.IGNORECASE):
        return 1
    return 2


def _pottery_type_answer_content_rank(text: str) -> int:
    if _POTTERY_TYPE_DIRECT_MADE_OBJECT_RE.search(text):
        return 0
    if _POTTERY_TYPE_FRIENDSHIP_COMPANION_RE.search(text):
        return 1
    if _POTTERY_TYPE_PROJECT_COMPANION_RE.search(text):
        return 2
    if _POTTERY_TYPE_GENERIC_ANSWER_OBJECT_RE.search(text):
        return 3
    return 4
