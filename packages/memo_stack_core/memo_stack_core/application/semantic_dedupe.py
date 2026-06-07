"""Conservative semantic duplicate checks for canonical memory facts."""

from __future__ import annotations

import unicodedata


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
    candidate_terms = semantic_memory_terms(candidate_text)
    existing_terms = semantic_memory_terms(existing_text)
    if len(candidate_terms) < 3 or len(existing_terms) < 3:
        return False
    if _has_negation_mismatch(candidate_text, existing_text):
        return False
    if _has_exclusive_anchor_mismatch(candidate_terms, existing_terms):
        return False
    overlap = candidate_terms & existing_terms
    if len(overlap) < 3:
        return False
    union = candidate_terms | existing_terms
    if len(overlap) / len(union) >= 0.6:
        return True
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
    return len(overlap & anchors) >= 2 and len(overlap) / min(
        len(candidate_terms),
        len(existing_terms),
    ) >= 0.75


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
    decision_terms = {
        "adapter",
        "backend",
        "cache",
        "canonical",
        "database",
        "engine",
        "memory",
        "model",
        "provider",
        "storage",
        "truth",
        "vector",
    }
    candidate_terms = meaningful_memory_terms(candidate_normalized)
    existing_terms = meaningful_memory_terms(existing_normalized)
    overlap = candidate_terms & existing_terms
    return len(overlap) >= 2 and bool(overlap & decision_terms)


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
