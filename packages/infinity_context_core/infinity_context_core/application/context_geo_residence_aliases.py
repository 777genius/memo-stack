"""Deterministic geo aliases for residence inference retrieval."""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_STATE_PHRASE_ALIASES: dict[str, tuple[str, ...]] = {
    "alabama": ("alabama",),
    "alaska": ("alaska",),
    "arizona": ("arizona",),
    "arkansas": ("arkansas",),
    "california": ("california",),
    "colorado": ("colorado",),
    "connecticut": ("connecticut",),
    "delaware": ("delaware",),
    "florida": ("florida",),
    "georgia": ("georgia",),
    "hawaii": ("hawaii",),
    "idaho": ("idaho",),
    "illinois": ("illinois",),
    "indiana": ("indiana",),
    "iowa": ("iowa",),
    "kansas": ("kansas",),
    "kentucky": ("kentucky",),
    "louisiana": ("louisiana",),
    "maine": ("maine",),
    "maryland": ("maryland",),
    "massachusetts": ("massachusetts",),
    "michigan": ("michigan",),
    "minnesota": ("minnesota",),
    "mississippi": ("mississippi",),
    "missouri": ("missouri",),
    "montana": ("montana",),
    "nebraska": ("nebraska",),
    "nevada": ("nevada",),
    "ohio": ("ohio",),
    "oklahoma": ("oklahoma",),
    "oregon": ("oregon",),
    "pennsylvania": ("pennsylvania",),
    "tennessee": ("tennessee",),
    "texas": ("texas",),
    "utah": ("utah",),
    "vermont": ("vermont",),
    "virginia": ("virginia",),
    "washington": ("washington",),
    "wisconsin": ("wisconsin",),
    "wyoming": ("wyoming",),
    "new york": ("new york",),
    "new jersey": ("new jersey",),
    "new mexico": ("new mexico",),
    "new hampshire": ("new hampshire",),
    "north carolina": ("north carolina",),
    "north dakota": ("north dakota",),
    "south carolina": ("south carolina",),
    "south dakota": ("south dakota",),
    "rhode island": ("rhode island",),
    "west virginia": ("west virginia",),
}

_STATE_TOKEN_ALIASES: dict[str, tuple[str, ...]] = {
    state: tuple(token for alias in aliases for token in alias.split())
    for state, aliases in _STATE_PHRASE_ALIASES.items()
}

_STATE_CITY_ALIASES: dict[str, tuple[str, ...]] = {
    "connecticut": ("stamford", "hartford", "bridgeport", "new haven"),
    "minnesota": ("voyageurs", "minneapolis", "st paul", "saint paul", "duluth"),
}

_LIVE_RESIDENCE_QUERY_TERMS = frozenset(
    {
        "live",
        "lives",
        "living",
        "reside",
        "resides",
        "residence",
    }
)
_LOCAL_ACTIVITY_EXPANSION_TERMS = (
    "local home address city town county moved relocated shelter adopted nearby"
)


def named_us_states_in_text(text: str) -> frozenset[str]:
    """Return canonical US state names explicitly present in text."""

    normalized = f" {text.casefold()} "
    states: set[str] = set()
    for state, aliases in _STATE_PHRASE_ALIASES.items():
        if any(_contains_phrase(normalized, alias) for alias in aliases):
            states.add(state)
    return frozenset(states)


def requests_named_state_residence(query: str) -> bool:
    """Return true when query asks residence against a named US state."""

    tokens = _token_set(query)
    return bool(tokens & _LIVE_RESIDENCE_QUERY_TERMS) and bool(
        named_us_states_in_text(query)
    )


def state_city_alias_terms(states: frozenset[str]) -> frozenset[str]:
    """Return tokenized city aliases for canonical state names."""

    aliases: set[str] = set()
    for state in states:
        for alias in _STATE_CITY_ALIASES.get(state, ()):
            aliases.update(alias.split())
    return frozenset(aliases)


def state_name_terms(states: frozenset[str]) -> frozenset[str]:
    """Return tokenized state aliases for canonical state names."""

    aliases: set[str] = set()
    for state in states:
        aliases.add(state)
        aliases.update(_STATE_TOKEN_ALIASES.get(state, ()))
    return frozenset(aliases)


def state_residence_expansion_suffix(query: str) -> str:
    """Return named-state city aliases used to widen residence retrieval."""

    states = named_us_states_in_text(query)
    if not states:
        return ""
    aliases: list[str] = []
    for state in sorted(states):
        aliases.append(state)
        aliases.extend(_STATE_CITY_ALIASES.get(state, ()))
    aliases.append(_LOCAL_ACTIVITY_EXPANSION_TERMS)
    return " ".join(aliases)


def _contains_phrase(normalized_text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", normalized_text) is not None


def _token_set(text: str) -> frozenset[str]:
    return frozenset(
        token
        for match in _TOKEN_RE.finditer(text)
        if len(token := match.group(0).casefold().strip("_")) >= 2
    )
