"""Conservative auto-memory admission and rule-based candidate extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass

from infinity_context_core.domain.entities import (
    Confidence,
    MemoryKind,
    SourceRef,
    TrustLevel,
)
from infinity_context_core.ports.auto_memory import (
    CandidateOperation,
    MemoryCandidate,
    MemoryClassifierPort,
    SourceProvenance,
)

_MAX_CANDIDATES = 5
_MAX_CANDIDATE_CHARS = 800
_ASSISTANT_SOURCES = {"ai_response", "assistant_answer", "assistant_summary"}
_ASSISTANT_ACTOR_ROLES = {"assistant"}
_ASSISTANT_AUTHORITIES = {"assistant_inference"}
_PREFIXES: tuple[tuple[re.Pattern[str], MemoryKind, str, str | None, str | None], ...] = (
    (
        re.compile(r"^\s*(?:remember|remember this|запомни|запомнить)\s*[:：-]\s*(.+)$", re.I),
        MemoryKind.NOTE,
        "explicit_remember_marker",
        None,
        None,
    ),
    (
        re.compile(
            (
                r"^\s*(?:decision|architecture decision|решение|"
                r"архитектурное решение)\s*[:：-]\s*(.+)$"
            ),
            re.I,
        ),
        MemoryKind.ARCHITECTURE_DECISION,
        "explicit_decision_marker",
        None,
        None,
    ),
    (
        re.compile(r"^\s*(?:constraint|ограничение|важное ограничение)\s*[:：-]\s*(.+)$", re.I),
        MemoryKind.CONSTRAINT,
        "explicit_constraint_marker",
        None,
        None,
    ),
    (
        re.compile(r"^\s*(?:preference|user preference|предпочтение)\s*[:：-]\s*(.+)$", re.I),
        MemoryKind.USER_PREFERENCE,
        "explicit_preference_marker",
        None,
        None,
    ),
    (
        re.compile(
            r"^\s*(?:current task|task note|текущая задача|заметка задачи)\s*[:：-]\s*(.+)$",
            re.I,
        ),
        MemoryKind.NOTE,
        "explicit_current_task_marker",
        "current_task",
        "task",
    ),
)
_PROMPT_INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions\b", re.I),
    re.compile(r"\b(system|developer)\s+prompt\b", re.I),
    re.compile(r"\breveal\s+(?:the\s+)?(?:system|developer)\s+(?:prompt|message)\b", re.I),
    re.compile(r"\bforget\s+(?:all\s+)?(?:rules|instructions)\b", re.I),
    re.compile(r"\bскрой\s+инструкц", re.I),
    re.compile(r"\bраскр(?:ой|ыть)\s+системн", re.I),
    re.compile(r"\bигнорируй\s+(?:все\s+)?(?:предыдущие|прошлые)\s+инструкц", re.I),
)
_UPDATE_PREFIXES = (
    "update memory",
    "update fact",
    "обнови память",
    "актуализируй память",
)
_DELETE_PREFIXES = (
    "forget",
    "delete memory",
    "remove memory",
    "забудь",
    "удали память",
)
_REVIEW_PREFIXES = (
    "review memory",
    "memory review",
    "проверь память",
)
_UPDATE_SPLITTER = re.compile(r"\s*(?:=>|->|→|\bshould now be\b|\bтеперь\b)\s*", re.I)


@dataclass(frozen=True)
class _SemanticPattern:
    pattern: re.Pattern[str]
    kind: MemoryKind
    reason: str
    confidence: Confidence = Confidence.LOW
    category: str | None = None
    ttl_policy: str | None = None
    text_prefix: str | None = None


_SEMANTIC_PATTERNS: tuple[_SemanticPattern, ...] = (
    _SemanticPattern(
        re.compile(r"^\s*(?:we\s+)?(?:decided|agreed)\s+(?:that\s+)?(.+)$", re.I),
        MemoryKind.ARCHITECTURE_DECISION,
        "semantic_decision_statement",
    ),
    _SemanticPattern(
        re.compile(
            r"^\s*(?:the\s+)?architecture decision\s+(?:is|was)\s+(?:to\s+)?(.+)$",
            re.I,
        ),
        MemoryKind.ARCHITECTURE_DECISION,
        "semantic_architecture_decision_statement",
    ),
    _SemanticPattern(
        re.compile(r"^\s*(?:мы\s+)?решили\s+(.+)$", re.I),
        MemoryKind.ARCHITECTURE_DECISION,
        "semantic_ru_decision_statement",
    ),
    _SemanticPattern(
        re.compile(r"^\s*архитектурное решение\s+(?:-|:|это|такое)?\s*(.+)$", re.I),
        MemoryKind.ARCHITECTURE_DECISION,
        "semantic_ru_architecture_decision_statement",
    ),
    _SemanticPattern(
        re.compile(
            r"^\s*(?:we\s+)?(?:must|should)\s+not\s+(store|log|send|persist|expose)\s+(.+)$",
            re.I,
        ),
        MemoryKind.CONSTRAINT,
        "semantic_negative_constraint_statement",
        text_prefix="Must not",
    ),
    _SemanticPattern(
        re.compile(r"^\s*(?:never|do\s+not|don't)\s+(store|log|send|persist|expose)\s+(.+)$", re.I),
        MemoryKind.CONSTRAINT,
        "semantic_imperative_constraint_statement",
        text_prefix="Must not",
    ),
    _SemanticPattern(
        re.compile(
            r"^\s*(?:нельзя|не\s+надо|запрещено)\s+"
            r"(хранить|логировать|отправлять|показывать|сохранять)\s+(.+)$",
            re.I,
        ),
        MemoryKind.CONSTRAINT,
        "semantic_ru_constraint_statement",
        text_prefix="Нельзя",
    ),
    _SemanticPattern(
        re.compile(r"^\s*i\s+prefer\s+(.+)$", re.I),
        MemoryKind.USER_PREFERENCE,
        "semantic_user_preference_statement",
    ),
    _SemanticPattern(
        re.compile(r"^\s*my\s+preference\s+is\s+(.+)$", re.I),
        MemoryKind.USER_PREFERENCE,
        "semantic_user_preference_statement",
    ),
    _SemanticPattern(
        re.compile(r"^\s*я\s+предпочитаю\s+(.+)$", re.I),
        MemoryKind.USER_PREFERENCE,
        "semantic_ru_user_preference_statement",
    ),
    _SemanticPattern(
        re.compile(r"^\s*(?:the\s+)?project\s+uses\s+(.+)$", re.I),
        MemoryKind.NOTE,
        "semantic_project_fact_statement",
    ),
    _SemanticPattern(
        re.compile(r"^\s*(?:infinity\s+context|this\s+project)\s+uses\s+(.+)$", re.I),
        MemoryKind.NOTE,
        "semantic_project_fact_statement",
    ),
    _SemanticPattern(
        re.compile(r"^\s*проект\s+использует\s+(.+)$", re.I),
        MemoryKind.NOTE,
        "semantic_ru_project_fact_statement",
    ),
    _SemanticPattern(
        re.compile(r"^\s*current\s+task\s+is\s+(?:to\s+)?(.+)$", re.I),
        MemoryKind.NOTE,
        "semantic_current_task_statement",
        category="current_task",
        ttl_policy="task",
    ),
    _SemanticPattern(
        re.compile(r"^\s*текущая\s+задача\s+(?:-|:|это|сейчас)?\s*(.+)$", re.I),
        MemoryKind.NOTE,
        "semantic_ru_current_task_statement",
        category="current_task",
        ttl_policy="task",
    ),
)


@dataclass(frozen=True)
class AdmissionDecision:
    outcome: str
    trust_level: TrustLevel
    confidence: Confidence
    reason: str


class MemoryAdmissionService:
    """Admission policy for unsafe auto-memory paths.

    Core Lite never auto-promotes classifier output. The decision is explicit so
    future policies can add auto-promote without changing ingest orchestration.
    """

    def decide(
        self,
        *,
        source: SourceProvenance,
        candidate: MemoryCandidate,
        allow_auto_promote: bool = False,
    ) -> AdmissionDecision:
        if not candidate.text.strip():
            return AdmissionDecision("ignore", TrustLevel.LOW, Confidence.LOW, "empty_candidate")
        if _looks_like_prompt_injection(candidate.text):
            return AdmissionDecision(
                "source_only",
                source.trust_level,
                Confidence.LOW,
                "prompt_injection_text",
            )
        if _is_assistant_derived_source(source):
            return AdmissionDecision(
                "create_suggestion",
                TrustLevel.LOW,
                Confidence.LOW,
                "assistant_low_trust",
            )
        if allow_auto_promote and source.trust_level == TrustLevel.HIGH:
            return AdmissionDecision(
                "create_active_fact",
                TrustLevel.HIGH,
                candidate.confidence,
                "manual_source",
            )
        return AdmissionDecision(
            "create_suggestion",
            source.trust_level,
            candidate.confidence,
            candidate.safe_reason,
        )


class NoopMemoryClassifier:
    async def classify(self, *, text: str, source: SourceProvenance) -> tuple[MemoryCandidate, ...]:
        return ()


class RuleBasedMemoryClassifier(MemoryClassifierPort):
    """Small deterministic classifier for explicit and high-signal memory markers.

    This is intentionally conservative. It produces candidates for explicit
    memory commands and a small set of durable semantic statements that are
    common in agent transcripts. Admission still keeps them review-gated.
    """

    async def classify(self, *, text: str, source: SourceProvenance) -> tuple[MemoryCandidate, ...]:
        candidates: list[MemoryCandidate] = []
        for line in _candidate_lines(text):
            candidate = _candidate_from_line(line=line, source=source)
            if candidate is not None:
                candidates.append(candidate)
            if len(candidates) >= _MAX_CANDIDATES:
                break
        return tuple(candidates)


def _candidate_from_line(
    *,
    line: str,
    source: SourceProvenance,
) -> MemoryCandidate | None:
    operation_candidate = _operation_candidate_from_line(line=line, source=source)
    if operation_candidate is not None:
        return operation_candidate
    for pattern, kind, reason, category, ttl_policy in _PREFIXES:
        match = pattern.match(line)
        if not match:
            continue
        text = _clean_candidate_text(match.group(1))
        if not text:
            return None
        return MemoryCandidate(
            text=text,
            kind=kind,
            confidence=Confidence.MEDIUM,
            source_refs=(
                SourceRef(
                    source_type=source.source_type,
                    source_id=source.source_id,
                    chunk_id=source.chunk_id,
                    quote_preview=text[:240],
                ),
            ),
            safe_reason=reason,
            category=category,
            ttl_policy=ttl_policy,
        )
    return _semantic_candidate_from_line(line=line, source=source)


def _semantic_candidate_from_line(
    *,
    line: str,
    source: SourceProvenance,
) -> MemoryCandidate | None:
    if _looks_like_prompt_injection(line):
        return None
    if _looks_like_question(line):
        return None
    for pattern in _SEMANTIC_PATTERNS:
        match = pattern.pattern.match(line)
        if not match:
            continue
        text = _semantic_text(pattern, match)
        if not text:
            return None
        return _memory_candidate(
            text=text,
            source=source,
            line=line,
            safe_reason=pattern.reason,
            operation=CandidateOperation.ADD,
            category=pattern.category,
            ttl_policy=pattern.ttl_policy,
            confidence=pattern.confidence,
            kind=pattern.kind,
        )
    return None


def _operation_candidate_from_line(
    *,
    line: str,
    source: SourceProvenance,
) -> MemoryCandidate | None:
    prefixed = _prefixed_payload(line, _UPDATE_PREFIXES)
    if prefixed is not None:
        parts = _UPDATE_SPLITTER.split(prefixed, maxsplit=1)
        if len(parts) != 2:
            return _review_candidate(
                text=prefixed,
                source=source,
                line=line,
                reason="explicit_update_needs_review",
            )
        target_hint = _clean_candidate_text(parts[0])
        updated_text = _clean_candidate_text(parts[1])
        if not target_hint or not updated_text:
            return None
        return _memory_candidate(
            text=updated_text,
            source=source,
            line=line,
            safe_reason="explicit_update_marker",
            operation=CandidateOperation.UPDATE,
            target_hint=target_hint,
            category="review",
            ttl_policy="review",
        )

    prefixed = _prefixed_payload(line, _DELETE_PREFIXES)
    if prefixed is not None:
        target_hint = _clean_candidate_text(prefixed)
        if not target_hint:
            return None
        return _memory_candidate(
            text=target_hint,
            source=source,
            line=line,
            safe_reason="explicit_delete_marker",
            operation=CandidateOperation.DELETE,
            target_hint=target_hint,
            category="delete_review",
            ttl_policy="delete_review",
        )

    prefixed = _prefixed_payload(line, _REVIEW_PREFIXES)
    if prefixed is not None:
        return _review_candidate(
            text=prefixed,
            source=source,
            line=line,
            reason="explicit_review_marker",
        )
    return None


def _review_candidate(
    *,
    text: str,
    source: SourceProvenance,
    line: str,
    reason: str,
) -> MemoryCandidate | None:
    cleaned = _clean_candidate_text(text)
    if not cleaned:
        return None
    return _memory_candidate(
        text=cleaned,
        source=source,
        line=line,
        safe_reason=reason,
        operation=CandidateOperation.REVIEW,
        category="review",
        ttl_policy="review",
        confidence=Confidence.LOW,
    )


def _memory_candidate(
    *,
    text: str,
    source: SourceProvenance,
    line: str,
    safe_reason: str,
    operation: CandidateOperation,
    category: str | None,
    ttl_policy: str | None,
    confidence: Confidence = Confidence.MEDIUM,
    kind: MemoryKind = MemoryKind.NOTE,
    target_hint: str | None = None,
) -> MemoryCandidate:
    return MemoryCandidate(
        text=text,
        kind=kind,
        confidence=confidence,
        source_refs=(
            SourceRef(
                source_type=source.source_type,
                source_id=source.source_id,
                chunk_id=source.chunk_id,
                quote_preview=line[:240],
            ),
        ),
        safe_reason=safe_reason,
        operation_hint=operation,
        category=category,
        ttl_policy=ttl_policy,
        target_hint=target_hint,
    )


def _prefixed_payload(line: str, prefixes: tuple[str, ...]) -> str | None:
    for prefix in prefixes:
        match = re.match(rf"^\s*{re.escape(prefix)}\s*[:：-]\s*(.+)$", line, re.I)
        if match:
            return match.group(1)
    return None


def _semantic_text(pattern: _SemanticPattern, match: re.Match[str]) -> str:
    if pattern.text_prefix:
        payload = " ".join(group for group in match.groups() if group)
        text = f"{pattern.text_prefix} {payload}"
    else:
        text = match.group(1)
    return _clean_candidate_text(text)


def _candidate_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if line:
            lines.append(line)
    if len(lines) == 1 and not _has_memory_prefix(lines[0]):
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    return lines


def _clean_candidate_text(text: str) -> str:
    return " ".join(text.strip().split())[:_MAX_CANDIDATE_CHARS].strip()


def _looks_like_prompt_injection(text: str) -> bool:
    return any(pattern.search(text) for pattern in _PROMPT_INJECTION_PATTERNS)


def _looks_like_question(text: str) -> bool:
    lowered = text.strip().casefold()
    if lowered.endswith("?"):
        return True
    return lowered.startswith(
        (
            "can ",
            "could ",
            "should ",
            "would ",
            "do i ",
            "do we ",
            "do you ",
            "do they ",
            "does ",
            "did ",
            "как ",
            "что ",
            "можно ",
            "нужно ли ",
        )
    )


def _has_memory_prefix(line: str) -> bool:
    return any(pattern.match(line) for pattern, _, _, _, _ in _PREFIXES)


def _is_assistant_derived_source(source: SourceProvenance) -> bool:
    actor_role = (source.actor_role or "").strip().lower()
    source_authority = (source.source_authority or "").strip().lower()
    return (
        source.source_type in _ASSISTANT_SOURCES
        or actor_role in _ASSISTANT_ACTOR_ROLES
        or source_authority in _ASSISTANT_AUTHORITIES
    )
