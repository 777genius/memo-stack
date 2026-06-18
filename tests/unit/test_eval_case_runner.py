from memo_stack_server.eval_case_runner import (
    _MAX_DIAGNOSTIC_MISMATCH_FAILURES,
    _case_failures,
    _required_diagnostic_mismatches,
)
from memo_stack_server.eval_types import EvalCase


def test_required_diagnostic_failures_are_bounded_and_redacted() -> None:
    raw_secret = "sk-proj-secretvalue1234567890"
    required = tuple(
        (f"diag_{index}", f"expected {raw_secret}")
        for index in range(_MAX_DIAGNOSTIC_MISMATCH_FAILURES + 4)
    )
    diagnostics = {
        f"diag_{index}": f"actual Bearer {raw_secret}"
        for index in range(_MAX_DIAGNOSTIC_MISMATCH_FAILURES + 4)
    }

    mismatches = _required_diagnostic_mismatches(diagnostics, required=required)
    failures = _case_failures(
        case=EvalCase(
            case_id="hybrid_document_beats_single_source",
            category="hybrid_retrieval",
            space_id="space_eval",
            memory_scope_ids=("scope_eval",),
            query="hybrid retrieval",
            required_diagnostics=required,
        ),
        recall_ok=True,
        precision_ok=True,
        evidence_guard=True,
        diagnostic_mismatches=mismatches,
        token_overflow=False,
        item_ids=("chunk_hybrid",),
    )

    rendered = repr(failures)
    assert len(mismatches) == _MAX_DIAGNOSTIC_MISMATCH_FAILURES
    assert mismatches[0]["key"] == "diag_0"
    assert raw_secret not in rendered
    assert "[redacted]" in rendered
    assert failures == (
        {
            "case_id": "hybrid_document_beats_single_source",
            "category": "hybrid_retrieval",
            "reason": "required_diagnostics_missing",
            "item_ids": ["chunk_hybrid"],
            "diagnostic_mismatches": list(mismatches),
        },
    )
