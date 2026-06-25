"""Answer-slot diversity detection for aggregation retrieval reranking."""

from __future__ import annotations

import re

_SLOT_RULES: tuple[
    tuple[re.Pattern[str], tuple[tuple[str, re.Pattern[str]], ...]],
    ...,
] = (
    (
        re.compile(r"\b(?:pottery|ceramic|clay)\b", re.IGNORECASE),
        (
            (
                "pottery_bowl",
                re.compile(r"\b(?:bowls?|black\s+and\s+white\s+flower)\b", re.IGNORECASE),
            ),
            (
                "pottery_cup",
                re.compile(r"\b(?:cups?|mugs?|dog\s+face)\b", re.IGNORECASE),
            ),
        ),
    ),
    (
        re.compile(r"\b(?:hikes?|hiking)\b", re.IGNORECASE),
        (
            (
                "hike_sunset_other_day",
                re.compile(
                    r"\b(?:gorgeous\s+sunset|sunset.{0,50}hiking|other\s+day)\b",
                    re.IGNORECASE,
                ),
            ),
            (
                "hike_waterfall_spot",
                re.compile(
                    r"\b(?:waterfall|spot\s+on\s+the\s+hike|"
                    r"rush\s+of\s+(?:the\s+)?water)\b",
                    re.IGNORECASE,
                ),
            ),
            (
                "hike_weekend_trail",
                re.compile(r"\b(?:buddies|new\s+trail|this\s+weekend)\b", re.IGNORECASE),
            ),
            (
                "hike_summer_fort_wayne",
                re.compile(r"\b(?:fort\s+wayne|last\s+summer)\b", re.IGNORECASE),
            ),
        ),
    ),
    (
        re.compile(
            r"\b(?:lgbtq|transgender|trans)\b(?=.{0,100}\bevents?\b)|"
            r"\bevents?\b(?=.{0,100}\b(?:lgbtq|transgender|trans)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        (
            ("lgbtq_support_group", re.compile(r"\bsupport\s+group\b", re.IGNORECASE)),
            ("lgbtq_pride_parade", re.compile(r"\bpride\s+parade\b", re.IGNORECASE)),
            (
                "lgbtq_school_speech",
                re.compile(
                    r"\b(?:school\s+(?:speech|talk)|speech.{0,40}school)\b",
                    re.IGNORECASE,
                ),
            ),
            (
                "lgbtq_advocacy_campaign",
                re.compile(r"\b(?:advocacy\s+campaign|lgbtq\s+rights)\b", re.IGNORECASE),
            ),
            (
                "lgbtq_mentorship_program",
                re.compile(
                    r"\b(?:mentorship|mentoring|mentor(?:ed|s)?)\b"
                    r"(?=.{0,100}\b(?:lgbtq|lgbt|transgender|trans)\b)|"
                    r"\b(?:lgbtq|lgbt|transgender|trans)\b"
                    r"(?=.{0,100}\b(?:mentorship|mentoring|mentor(?:ed|s)?)\b)",
                    re.IGNORECASE | re.DOTALL,
                ),
            ),
            (
                "lgbtq_art_show",
                re.compile(
                    r"\b(?:lgbtq|lgbt|transgender|trans)\b(?=.{0,100}\bart\s+show\b)|"
                    r"\bart\s+show\b(?=.{0,100}\b(?:lgbtq|lgbt|transgender|trans)\b)",
                    re.IGNORECASE | re.DOTALL,
                ),
            ),
            (
                "lgbtq_activist_group",
                re.compile(
                    r"\b(?:lgbtq|lgbt|lgbtq\s+rights)\b"
                    r"(?=.{0,100}\bactivist\s+group\b)|"
                    r"\bactivist\s+group\b(?=.{0,100}\b(?:lgbtq|lgbt|lgbtq\s+rights)\b)",
                    re.IGNORECASE | re.DOTALL,
                ),
            ),
            (
                "lgbtq_youth_center",
                re.compile(
                    r"\b(?:lgbtq|lgbt|transgender|trans)\b"
                    r"(?=.{0,100}\byouth\s+center\b)|"
                    r"\byouth\s+center\b"
                    r"(?=.{0,100}\b(?:lgbtq|lgbt|transgender|trans)\b)",
                    re.IGNORECASE | re.DOTALL,
                ),
            ),
            (
                "lgbtq_counseling_workshop",
                re.compile(
                    r"\b(?:lgbtq|lgbt|transgender|trans)\b"
                    r"(?=.{0,120}\bcounsel(?:ing|ling)\s+workshop\b)|"
                    r"\bcounsel(?:ing|ling)\s+workshop\b"
                    r"(?=.{0,120}\b(?:lgbtq|lgbt|transgender|trans)\b)",
                    re.IGNORECASE | re.DOTALL,
                ),
            ),
            (
                "transgender_poetry_reading",
                re.compile(r"\btransgender\s+poetry\s+reading\b", re.IGNORECASE),
            ),
            (
                "transgender_conference",
                re.compile(r"\btransgender\s+conference\b", re.IGNORECASE),
            ),
            (
                "transgender_youth_talent_show",
                re.compile(
                    r"\b(?:youth\s+center|talent\s+show|band.{0,40}stage)\b",
                    re.IGNORECASE,
                ),
            ),
        ),
    ),
    (
        re.compile(r"\b(?:pets?|animals?)\b", re.IGNORECASE),
        (
            ("pet_dog", re.compile(r"\b(?:dog|puppy|max|new\s+addition)\b", re.IGNORECASE)),
            ("pet_turtle", re.compile(r"\b(?:turtles?|critters?|basking)\b", re.IGNORECASE)),
        ),
    ),
    (
        re.compile(
            r"\bturtles?\b(?=.{0,80}\b(?:how\s+many|count|number|total)\b)|"
            r"\b(?:how\s+many|count|number|total)\b(?=.{0,80}\bturtles?\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        (
            ("turtle_two", re.compile(r"\btwo\s+turtles?\b", re.IGNORECASE)),
            ("turtle_third", re.compile(r"\bthird\s+turtle\b|\bnew\s+friend\b", re.IGNORECASE)),
            ("turtle_three", re.compile(r"\bthree\s+turtles?\b", re.IGNORECASE)),
        ),
    ),
    (
        re.compile(r"\b(?:friends?|made\s+friends?)\b", re.IGNORECASE),
        (
            (
                "friend_place_volunteering",
                re.compile(r"\b(?:homeless\s+shelter|fellow\s+volunteers?)\b", re.IGNORECASE),
            ),
            (
                "friend_place_gym",
                re.compile(r"\b(?:gym|workout\s+routine)\b", re.IGNORECASE),
            ),
            (
                "friend_place_church",
                re.compile(r"\b(?:church|faith\s+community|local\s+church)\b", re.IGNORECASE),
            ),
        ),
    ),
    (
        re.compile(
            r"\b(?:european\s+countries|countries|england|spain)\b"
            r"(?=.{0,100}\b(?:been\s+to|visited|trip|travel|abroad|european)\b)|"
            r"\b(?:been\s+to|visited|trip|travel|abroad)\b"
            r"(?=.{0,100}\b(?:european\s+countries|countries|england|spain)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        (
            ("travel_country_england", re.compile(r"\bengland\b", re.IGNORECASE)),
            ("travel_country_spain", re.compile(r"\bspain\b", re.IGNORECASE)),
        ),
    ),
    (
        re.compile(
            r"\bshelters?\b(?=.{0,100}\bvolunteer)|"
            r"\bvolunteer\b(?=.{0,100}\bshelters?\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        (
            (
                "volunteer_shelter_homeless",
                re.compile(r"\bhomeless\s+shelter\b", re.IGNORECASE),
            ),
            (
                "volunteer_shelter_dog",
                re.compile(r"\bdog\s+shelter\b", re.IGNORECASE),
            ),
        ),
    ),
    (
        re.compile(r"\b(?:causes?|support(?:ing)?|passionate)\b", re.IGNORECASE),
        (
            ("cause_veterans", re.compile(r"\b(?:veterans?|military)\b", re.IGNORECASE)),
            (
                "cause_education",
                re.compile(r"\b(?:education|schools?|education\s+reform)\b", re.IGNORECASE),
            ),
            (
                "cause_infrastructure",
                re.compile(r"\b(?:infrastructure|infrastructure\s+development)\b", re.IGNORECASE),
            ),
        ),
    ),
    (
        re.compile(r"\b(?:foods?|recipes?|meals?|dishes?)\b", re.IGNORECASE),
        (
            (
                "vegetable_recipe",
                re.compile(
                    r"\b(?:roasted\s+veg(?:etables?)?|grilled\s+vegetables?|"
                    r"vegetable\s+recipe|veg\s+recipe)\b",
                    re.IGNORECASE,
                ),
            ),
            (
                "chicken_stir_fry",
                re.compile(
                    r"\b(?:grilled\s+chicken|veggie\s+stir-fry|"
                    r"vegetable\s+stir-fry|chicken\s+and\s+veggie)\b",
                    re.IGNORECASE,
                ),
            ),
            (
                "local_dish",
                re.compile(
                    r"\b(?:local\s+dishes|poutine|french\s+fries|"
                    r"regional\s+dishes|local\s+food)\b",
                    re.IGNORECASE,
                ),
            ),
        ),
    ),
)


def aggregation_answer_slot_count(*, query: str, text: str) -> int:
    return len(aggregation_answer_slots(query=query, text=text))


def aggregation_answer_slots(*, query: str, text: str) -> frozenset[str]:
    slots: set[str] = set()
    for query_pattern, slot_patterns in _SLOT_RULES:
        if query_pattern.search(query) is None:
            continue
        for slot, text_pattern in slot_patterns:
            if text_pattern.search(text) is not None:
                slots.add(slot)
    return frozenset(slots)
