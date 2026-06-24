"""Shared answer-evidence signal contracts for deterministic reranking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerEvidenceSignal:
    """Bounded score adjustment for an item's answer-evidence fit."""

    boost: float = 0.0
    penalty: float = 0.0
    reason: str = ""
