"""Ports and DTOs for review-gated auto-memory extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memory_core.domain.entities import Confidence, MemoryKind, SourceRef, TrustLevel


@dataclass(frozen=True)
class SourceProvenance:
    source_type: str
    source_id: str
    trust_level: TrustLevel
    chunk_id: str | None = None


@dataclass(frozen=True)
class MemoryCandidate:
    text: str
    kind: MemoryKind
    confidence: Confidence
    source_refs: tuple[SourceRef, ...]
    safe_reason: str


class MemoryClassifierPort(Protocol):
    async def classify(self, *, text: str, source: SourceProvenance) -> tuple[MemoryCandidate, ...]:
        """Return fact candidates that still require admission/review."""


class FactExtractionPort(Protocol):
    async def extract_facts(
        self,
        *,
        text: str,
        source: SourceProvenance,
    ) -> tuple[MemoryCandidate, ...]:
        """Extract candidate facts. Implementations must not write active facts directly."""
