"""Shared review payload contracts for memory suggestions."""

from __future__ import annotations

from typing import Any

CONFLICT_REVIEW_KIND = "conflict_review"
DUPLICATE_FACT_MERGE_REVIEW_KIND = "duplicate_fact_merge"


def conflict_review_contract(*, approve_effect: str) -> dict[str, Any]:
    return {
        "review_kind": CONFLICT_REVIEW_KIND,
        "recommended_action": "manual_conflict_review",
        "default_resolution": "reject_or_edit_before_approve",
        "resolution_options": [
            {
                "id": "reject_candidate",
                "review_action": "reject",
                "effect": "keep_existing_fact",
                "availability": "available",
            },
            {
                "id": "approve_candidate",
                "review_action": "approve",
                "effect": approve_effect,
                "availability": "available",
            },
            {
                "id": "expire_candidate",
                "review_action": "expire",
                "effect": "hide_pending_suggestion",
                "availability": "available",
            },
            {
                "id": "replace_existing_fact",
                "review_action": "manual_targeted_update",
                "effect": "update_conflicting_fact_with_candidate",
                "availability": "manual_only",
            },
        ],
    }
