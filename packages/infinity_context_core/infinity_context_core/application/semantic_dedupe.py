"""Conservative semantic duplicate checks for canonical memory facts."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from infinity_context_core.application.anchor_extraction import extract_observed_anchors
from infinity_context_core.domain.entities import MemoryAnchorKind


@dataclass(frozen=True)
class FactDuplicateMatch:
    match_type: str
    score: float
    reason_codes: tuple[str, ...]
    overlap_terms: tuple[str, ...]


def normalize_memory_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    return " ".join(normalized.strip().casefold().split())


def meaningful_memory_terms(text: str) -> set[str]:
    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "use",
        "uses",
        "user",
        "decided",
        "should",
        "memory",
    }
    return {
        token.strip(".,:;!?()[]{}\"'")
        for token in text.split()
        if len(token.strip(".,:;!?()[]{}\"'")) >= 4
        and token.strip(".,:;!?()[]{}\"'") not in stop_words
    }


def looks_equivalent_fact(candidate_text: str, existing_text: str) -> bool:
    return describe_duplicate_fact_match(candidate_text, existing_text) is not None


def describe_duplicate_fact_match(
    candidate_text: str,
    existing_text: str,
) -> FactDuplicateMatch | None:
    candidate_normalized = normalize_memory_text(candidate_text)
    existing_normalized = normalize_memory_text(existing_text)
    if not candidate_normalized or not existing_normalized:
        return None
    if candidate_normalized == existing_normalized:
        return FactDuplicateMatch(
            match_type="exact_normalized_text",
            score=1.0,
            reason_codes=("exact_normalized_text",),
            overlap_terms=tuple(sorted(semantic_memory_terms(candidate_text))),
        )
    candidate_terms = semantic_memory_terms(candidate_text)
    existing_terms = semantic_memory_terms(existing_text)
    if len(candidate_terms) < 3 or len(existing_terms) < 3:
        return None
    if _has_negation_mismatch(candidate_text, existing_text):
        return None
    if _has_named_anchor_mismatch(candidate_text, existing_text):
        return None
    if _has_event_identity_mismatch(candidate_text, existing_text):
        return None
    if _has_exclusive_anchor_mismatch(candidate_terms, existing_terms):
        return None
    overlap = candidate_terms & existing_terms
    if len(overlap) < 3:
        return None
    union = candidate_terms | existing_terms
    score = len(overlap) / len(union)
    if score >= 0.6:
        return FactDuplicateMatch(
            match_type="semantic_token_overlap",
            score=round(score, 3),
            reason_codes=("semantic_duplicate", "token_overlap"),
            overlap_terms=tuple(sorted(overlap))[:12],
        )
    anchors = {
        "adapter",
        "canonical",
        "cognee",
        "database",
        "document",
        "graph",
        "graphiti",
        "memory",
        "mcp",
        "neo4j",
        "postgres",
        "qdrant",
        "rag",
        "temporal",
        "truth",
        "vector",
    }
    anchor_score = len(overlap) / min(
        len(candidate_terms),
        len(existing_terms),
    )
    if len(overlap & anchors) >= 2 and anchor_score >= 0.75:
        return FactDuplicateMatch(
            match_type="semantic_anchor_overlap",
            score=round(max(score, anchor_score * 0.92), 3),
            reason_codes=("semantic_duplicate", "anchor_overlap"),
            overlap_terms=tuple(sorted(overlap))[:12],
        )
    return None


def semantic_memory_terms(text: str) -> set[str]:
    aliases = {
        "docs": "document",
        "doc": "document",
        "documents": "document",
        "graphs": "graph",
        "memories": "memory",
        "notes": "note",
        "retrieves": "retrieval",
        "vectors": "vector",
    }
    terms: set[str] = set()
    for raw_token in normalize_memory_text(text).split():
        token = raw_token.strip(".,:;!?()[]{}\"'")
        if not token:
            continue
        token = aliases.get(token, token)
        if token.endswith("s") and len(token) > 5 and token not in {"postgres", "redis"}:
            token = token[:-1]
        if token in {
            "about",
            "again",
            "already",
            "decided",
            "durable",
            "fact",
            "only",
            "should",
            "store",
            "that",
            "this",
            "use",
            "uses",
            "using",
            "with",
        }:
            continue
        if len(token) >= 4:
            terms.add(token)
    return terms


def looks_conflicting_fact(candidate_text: str, existing_text: str) -> bool:
    candidate_normalized = normalize_memory_text(candidate_text)
    existing_normalized = normalize_memory_text(existing_text)
    if not candidate_normalized or not existing_normalized:
        return False
    if candidate_normalized == existing_normalized:
        return False
    if looks_equivalent_fact(candidate_normalized, existing_normalized):
        return False
    decision_terms = {
        "adapter",
        "backend",
        "cache",
        "canonical",
        "cognee",
        "database",
        "engine",
        "graphiti",
        "memory",
        "model",
        "neo4j",
        "postgres",
        "provider",
        "qdrant",
        "rag",
        "storage",
        "truth",
        "vector",
    }
    candidate_terms = semantic_memory_terms(candidate_normalized)
    existing_terms = semantic_memory_terms(existing_normalized)
    overlap = candidate_terms & existing_terms
    if len(overlap) < 2:
        return False
    if _has_named_anchor_mismatch(candidate_text, existing_text):
        return False
    if _has_event_identity_mismatch(candidate_text, existing_text):
        return False
    if _has_negation_mismatch(candidate_normalized, existing_normalized):
        return bool(overlap & decision_terms) or len(overlap) >= 3
    if _has_exclusive_anchor_mismatch(candidate_terms, existing_terms):
        return bool(overlap & decision_terms)
    return bool(overlap & decision_terms) and len(overlap) >= 3


def _has_negation_mismatch(candidate_text: str, existing_text: str) -> bool:
    negation_terms = {"avoid", "disable", "disabled", "except", "never", "not", "without"}
    candidate_has_negation = bool(
        set(normalize_memory_text(candidate_text).split()) & negation_terms
    )
    existing_has_negation = bool(
        set(normalize_memory_text(existing_text).split()) & negation_terms
    )
    return candidate_has_negation != existing_has_negation


def _has_exclusive_anchor_mismatch(
    candidate_terms: set[str],
    existing_terms: set[str],
) -> bool:
    engines = {"cognee", "graphiti", "mysql", "neo4j", "postgres", "qdrant", "redis", "sqlite"}
    candidate_engines = candidate_terms & engines
    existing_engines = existing_terms & engines
    return bool(candidate_engines and existing_engines and not candidate_engines & existing_engines)


def _has_named_anchor_mismatch(candidate_text: str, existing_text: str) -> bool:
    candidate_projects = _named_anchor_keys(
        candidate_text,
        kind=MemoryAnchorKind.PROJECT,
        reasons={"explicit project reference"},
    )
    existing_projects = _named_anchor_keys(
        existing_text,
        kind=MemoryAnchorKind.PROJECT,
        reasons={"explicit project reference"},
    )
    if candidate_projects and existing_projects and not candidate_projects & existing_projects:
        return True

    if _has_event_anchor(candidate_text) and _has_event_anchor(existing_text):
        candidate_people = _named_anchor_keys(candidate_text, kind=MemoryAnchorKind.PERSON)
        existing_people = _named_anchor_keys(existing_text, kind=MemoryAnchorKind.PERSON)
        if candidate_people and existing_people and not candidate_people & existing_people:
            return True

    candidate_orgs = _named_anchor_keys(candidate_text, kind=MemoryAnchorKind.ORGANIZATION)
    existing_orgs = _named_anchor_keys(existing_text, kind=MemoryAnchorKind.ORGANIZATION)
    return bool(candidate_orgs and existing_orgs and not candidate_orgs & existing_orgs)


def _has_event_identity_mismatch(candidate_text: str, existing_text: str) -> bool:
    candidate_events = _event_identity_payloads(candidate_text)
    existing_events = _event_identity_payloads(existing_text)
    if not candidate_events or not existing_events:
        return False
    for candidate in candidate_events:
        for existing in existing_events:
            if _event_payloads_compatible(candidate, existing):
                return False
    return True


def _event_identity_payloads(text: str) -> tuple[dict[str, str], ...]:
    payloads: list[dict[str, str]] = []
    for anchor in extract_observed_anchors(text):
        if anchor.kind != MemoryAnchorKind.EVENT:
            continue
        metadata = anchor.metadata
        payload = {
            "event_type": str(metadata.get("event_type_canonical") or ""),
            "participant": str(metadata.get("event_participant_canonical_key") or ""),
            "temporal": _event_temporal_identity(metadata),
        }
        if any(payload.values()):
            payloads.append(payload)
    return tuple(payloads)


def _event_payloads_compatible(candidate: dict[str, str], existing: dict[str, str]) -> bool:
    for key in ("event_type", "participant", "temporal"):
        left = candidate.get(key, "")
        right = existing.get(key, "")
        if left and right and left != right:
            return False
    return True


def _event_temporal_identity(metadata: dict[str, object]) -> str:
    code = str(metadata.get("event_temporal_hint_code") or "")
    if not code:
        return ""
    quantity = metadata.get("event_temporal_quantity")
    unit = str(metadata.get("event_temporal_unit") or "")
    return f"{code}:{quantity}:{unit}" if quantity is not None and unit else code


def _named_anchor_keys(
    text: str,
    *,
    kind: MemoryAnchorKind,
    reasons: set[str] | None = None,
) -> set[str]:
    return {
        anchor.normalized_key
        for anchor in extract_observed_anchors(text)
        if anchor.kind == kind and (reasons is None or anchor.reason in reasons)
    }


def _has_event_anchor(text: str) -> bool:
    return any(anchor.kind == MemoryAnchorKind.EVENT for anchor in extract_observed_anchors(text))
