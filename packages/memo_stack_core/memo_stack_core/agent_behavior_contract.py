"""Shared contract for publishable Memo Stack agent-behavior evidence."""

from __future__ import annotations

LIVE_SESSION_TAG = "live_session"
ADVERSARIAL_TAG = "adversarial"
TRANSCRIPT_CORPUS_TAG = "transcript_corpus"
EXTERNAL_TRANSCRIPT_TAG = "external_transcript"

AGENT_BEHAVIOR_TOP_EVIDENCE_SCENARIO_SET = "all"
AGENT_BEHAVIOR_TOP_EVIDENCE_SCENARIO_IDS = (
    "new_fact",
    "duplicate_fact",
    "update_outdated_fact",
    "version_conflict",
    "explicit_forget",
    "do_not_remember",
    "secret_in_message",
    "prompt_injection",
    "document_vs_fact",
    "cross_project_isolation",
    "answer_support",
    "stale_hidden",
    "deleted_hidden",
    "restricted_classification",
    "batch_proposal_conflict",
    "low_confidence_claim",
    "remember_later_ambiguous",
    "tool_overuse_guard",
    "multi_turn_correction",
    "memory_as_evidence",
    "real_noisy_transcript_update",
    "real_paraphrase_duplicate",
    "real_secret_in_long_notes",
    "real_similar_project_isolation",
    "real_thread_neighbor_isolation",
    "real_ambiguous_forget_multiple_matches",
    "real_interview_stream_extract_fact",
    "real_retrieved_memory_injection_no_write",
    "real_secret_search_trap",
    "real_immediate_recall_after_write",
    "live_long_transcript_rollup",
    "live_update_delete_chain",
    "live_review_gated_uncertain_transcript",
    "live_cross_memory_scope_meeting_noise",
    "live_transcript_secret_injection_trap",
    "live_long_tail_recall_after_document",
    "transcript_architecture_drift_rollup",
    "transcript_handoff_tail_recall",
    "transcript_rejected_approach_update",
    "transcript_confirmed_delete_only_one_fact",
    "transcript_secret_tool_output_no_memory_write",
)
AGENT_BEHAVIOR_TOP_EVIDENCE_CASE_COUNT_FLOORS = {
    "scenario_count": len(AGENT_BEHAVIOR_TOP_EVIDENCE_SCENARIO_IDS),
    "live_session_case_count": 11,
    "transcript_corpus_case_count": 5,
    "adversarial_case_count": 9,
}
AGENT_BEHAVIOR_TOP_EVIDENCE_SCENARIO_TAG_METRICS = {
    "live_session_case_count": LIVE_SESSION_TAG,
    "transcript_corpus_case_count": TRANSCRIPT_CORPUS_TAG,
    "adversarial_case_count": ADVERSARIAL_TAG,
}
AGENT_BEHAVIOR_TOP_EVIDENCE_SCENARIO_INTEGRITY_CHECKS = (
    "scenario_reports_well_formed",
    "scenario_report_ids_present",
    "scenario_report_ids_unique",
    "scenario_reports_all_passed",
    "canonical_scenario_ids_present",
)
