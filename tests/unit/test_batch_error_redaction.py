import asyncio

from memo_stack_core.application.dto import (
    CreateSuggestionCommand,
    CreateSuggestionsBatchCommand,
    ReviewContextLinkSuggestionBatchItemCommand,
    ReviewContextLinkSuggestionsBatchCommand,
    ReviewSuggestionBatchItemCommand,
    ReviewSuggestionsBatchCommand,
)
from memo_stack_core.application.use_cases.context_link_reviews import (
    ReviewContextLinkSuggestionsBatchUseCase,
)
from memo_stack_core.application.use_cases.suggestions import (
    CreateSuggestionsBatchUseCase,
    ReviewSuggestionsBatchUseCase,
)
from memo_stack_core.domain.entities import MemoryKind, MemoryScopeId, SourceRef, SpaceId
from memo_stack_core.domain.errors import MemoryValidationError


class _FailingUseCase:
    async def execute(self, _command):
        raise MemoryValidationError(
            "provider failed with Authorization: Bearer sk-proj-batch-secret-value"
        )


class _CountingUseCase:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, _command):
        self.calls += 1
        raise AssertionError("duplicate batch should fail before item review")


def test_create_suggestions_batch_redacts_item_error_messages() -> None:
    result = asyncio.run(_run_create_suggestions_batch_redaction_case())

    assert result.failed == 1
    assert "sk-proj-batch-secret-value" not in (result.results[0].error_message or "")
    assert "[redacted]" in (result.results[0].error_message or "")


async def _run_create_suggestions_batch_redaction_case():
    use_case = CreateSuggestionsBatchUseCase(create_suggestion=_FailingUseCase())

    return await use_case.execute(
        CreateSuggestionsBatchCommand(
            items=(
                CreateSuggestionCommand(
                    space_id=SpaceId("space_1"),
                    memory_scope_id=MemoryScopeId("scope_1"),
                    candidate_text="Batch redaction candidate",
                    kind=MemoryKind.NOTE,
                    source_refs=(SourceRef(source_type="manual", source_id="src_1"),),
                    safe_reason="unit redaction",
                ),
            ),
            continue_on_error=True,
        )
    )


def test_review_suggestions_batch_rejects_duplicate_ids_before_review() -> None:
    reviewer = _CountingUseCase()
    use_case = ReviewSuggestionsBatchUseCase(
        approve_suggestion=reviewer,
        reject_suggestion=reviewer,
        expire_suggestion=reviewer,
    )

    try:
        asyncio.run(
            use_case.execute(
                ReviewSuggestionsBatchCommand(
                    items=(
                        ReviewSuggestionBatchItemCommand(
                            suggestion_id="sug_duplicate",
                            action="approve",
                        ),
                        ReviewSuggestionBatchItemCommand(
                            suggestion_id="sug_duplicate",
                            action="reject",
                        ),
                    ),
                    continue_on_error=True,
                )
            )
        )
    except MemoryValidationError as exc:
        assert "duplicate suggestion_id" in str(exc)
    else:
        raise AssertionError("Expected duplicate suggestion_id to fail validation")

    assert reviewer.calls == 0


def test_context_link_batch_redacts_item_error_messages() -> None:
    result = asyncio.run(_run_context_link_batch_redaction_case())

    assert result.failed == 1
    assert "sk-proj-batch-secret-value" not in (result.results[0].error_message or "")
    assert "[redacted]" in (result.results[0].error_message or "")


def test_context_link_batch_rejects_duplicate_ids_before_review() -> None:
    reviewer = _CountingUseCase()
    use_case = ReviewContextLinkSuggestionsBatchUseCase(review_context_link_suggestion=reviewer)

    try:
        asyncio.run(
            use_case.execute(
                ReviewContextLinkSuggestionsBatchCommand(
                    items=(
                        ReviewContextLinkSuggestionBatchItemCommand(
                            suggestion_id="ctxsug_duplicate",
                            action="approve",
                        ),
                        ReviewContextLinkSuggestionBatchItemCommand(
                            suggestion_id="ctxsug_duplicate",
                            action="reject",
                        ),
                    ),
                    continue_on_error=True,
                )
            )
        )
    except MemoryValidationError as exc:
        assert "duplicate suggestion_id" in str(exc)
    else:
        raise AssertionError("Expected duplicate suggestion_id to fail validation")

    assert reviewer.calls == 0


async def _run_context_link_batch_redaction_case():
    use_case = ReviewContextLinkSuggestionsBatchUseCase(
        review_context_link_suggestion=_FailingUseCase()
    )

    return await use_case.execute(
        ReviewContextLinkSuggestionsBatchCommand(
            items=(
                ReviewContextLinkSuggestionBatchItemCommand(
                    suggestion_id="ctxsug_1",
                    action="approve",
                ),
            ),
            continue_on_error=True,
        )
    )
