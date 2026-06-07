import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from memo_stack_core.application import ConsolidateCaptureCommand, ConsolidateCaptureUseCase
from memo_stack_core.domain.entities import Confidence, MemoryKind, SourceRef
from memo_stack_core.ports.auto_memory import CandidateOperation, MemoryCandidate, SourceProvenance
from memo_stack_server.config import CaptureMode, DeployProfile, Settings
from memo_stack_server.main import create_app


class StaticExtractor:
    version = "semantic-dedupe-test-extractor-v1"
    prompt_version = "semantic-dedupe-test-prompt-v1"
    requires_external_ai = False

    def __init__(self, candidates: tuple[MemoryCandidate, ...]) -> None:
        self._candidates = candidates

    async def extract_facts(
        self,
        *,
        text: str,
        source: SourceProvenance,
    ) -> tuple[MemoryCandidate, ...]:
        return self._candidates


def test_capture_semantic_active_duplicate_creates_no_suggestion_or_fact(
    tmp_path: Path,
) -> None:
    app = _capture_app(tmp_path, "capture-semantic-duplicate.db", CaptureMode.AUTO_APPLY_SAFE)
    headers = {"Authorization": "Bearer test-token"}
    with TestClient(app) as client:
        existing = _create_fact(
            client,
            headers=headers,
            text="Qdrant owns document vector retrieval.",
            space_slug="capture-semantic-duplicate",
        )
        capture = _create_capture(
            client,
            headers=headers,
            text="Remember: Docs retrieval should use Qdrant vectors.",
            space_slug="capture-semantic-duplicate",
        )
        result = _consolidate(
            client,
            capture_id=capture.json()["data"]["id"],
            extractor=StaticExtractor(
                (
                    _candidate(
                        "Docs retrieval should use Qdrant vectors.",
                        confidence=Confidence.HIGH,
                        ttl_policy="durable",
                    ),
                )
            ),
            auto_apply_safe_enabled=True,
        )
        facts = _list_facts(client, headers=headers, space_slug="capture-semantic-duplicate")
        suggestions = _list_suggestions(
            client,
            headers=headers,
            space_slug="capture-semantic-duplicate",
        )

    assert existing.status_code == 201
    assert result.auto_applied_facts == 0
    assert result.created_suggestions == 0
    assert [item["text"] for item in facts.json()["data"]] == [
        "Qdrant owns document vector retrieval."
    ]
    assert suggestions.json()["data"] == []


def test_capture_semantic_dedupe_keeps_engine_mismatch_for_review(tmp_path: Path) -> None:
    app = _capture_app(tmp_path, "capture-semantic-engine-mismatch.db", CaptureMode.SUGGEST)
    headers = {"Authorization": "Bearer test-token"}
    with TestClient(app) as client:
        _create_fact(
            client,
            headers=headers,
            text="Postgres owns document vector retrieval.",
            space_slug="capture-semantic-engine-mismatch",
        )
        capture = _create_capture(
            client,
            headers=headers,
            text="Remember: Docs retrieval should use Qdrant vectors.",
            space_slug="capture-semantic-engine-mismatch",
        )
        result = _consolidate(
            client,
            capture_id=capture.json()["data"]["id"],
            extractor=StaticExtractor(
                (_candidate("Docs retrieval should use Qdrant vectors."),)
            ),
            auto_apply_safe_enabled=False,
        )
        suggestions = _list_suggestions(
            client,
            headers=headers,
            space_slug="capture-semantic-engine-mismatch",
        )

    assert result.created_suggestions == 1
    assert suggestions.json()["data"][0]["candidate_text"] == (
        "Docs retrieval should use Qdrant vectors."
    )


def test_auto_apply_safe_active_conflict_creates_review_suggestion_not_fact(
    tmp_path: Path,
) -> None:
    app = _capture_app(tmp_path, "capture-semantic-active-conflict.db", CaptureMode.AUTO_APPLY_SAFE)
    headers = {"Authorization": "Bearer test-token"}
    with TestClient(app) as client:
        existing = _create_fact(
            client,
            headers=headers,
            text="Postgres owns document vector retrieval.",
            space_slug="capture-semantic-active-conflict",
        )
        capture = _create_capture(
            client,
            headers=headers,
            text="Remember: Docs retrieval should use Qdrant vectors.",
            space_slug="capture-semantic-active-conflict",
        )
        result = _consolidate(
            client,
            capture_id=capture.json()["data"]["id"],
            extractor=StaticExtractor(
                (
                    _candidate(
                        "Docs retrieval should use Qdrant vectors.",
                        confidence=Confidence.HIGH,
                        ttl_policy="durable",
                    ),
                )
            ),
            auto_apply_safe_enabled=True,
        )
        facts = _list_facts(client, headers=headers, space_slug="capture-semantic-active-conflict")
        suggestions = _list_suggestions(
            client,
            headers=headers,
            space_slug="capture-semantic-active-conflict",
        )

    assert existing.status_code == 201
    assert result.auto_applied_facts == 0
    assert result.created_suggestions == 1
    assert [item["text"] for item in facts.json()["data"]] == [
        "Postgres owns document vector retrieval."
    ]

    suggestion = suggestions.json()["data"][0]
    assert suggestion["candidate_text"] == "Docs retrieval should use Qdrant vectors."
    assert suggestion["review_payload"]["conflicting_fact_id"] == existing.json()["data"]["id"]
    assert suggestion["review_payload"]["conflicting_fact_version"] == 1
    assert "auto_apply_active_conflict" in suggestion["review_payload"][
        "rejected_resolver_codes"
    ]


def _capture_app(tmp_path: Path, database_name: str, capture_mode: CaptureMode):
    return create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{tmp_path / database_name}",
            auto_create_schema=True,
            service_token="test-token",
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
            capture_mode=capture_mode,
        )
    )


def _create_fact(
    client: TestClient,
    *,
    headers: dict[str, str],
    text: str,
    space_slug: str,
):
    return client.post(
        "/v1/facts",
        json={
            "space_slug": space_slug,
            "profile_external_ref": "default",
            "text": text,
            "kind": "note",
            "source_refs": [{"source_type": "manual", "source_id": "semantic-dedupe-test"}],
        },
        headers=headers,
    )


def _create_capture(
    client: TestClient,
    *,
    headers: dict[str, str],
    text: str,
    space_slug: str,
):
    return client.post(
        "/v1/captures",
        json={
            "space_slug": space_slug,
            "profile_external_ref": "default",
            "source_agent": "codex",
            "source_kind": "hook",
            "event_type": "UserPromptSubmit",
            "actor_role": "user",
            "source_event_id": text,
            "text": text,
            "trust_level": "high",
            "source_authority": "explicit_user_command",
            "sensitivity": "low",
            "consolidate": True,
        },
        headers=headers,
    )


def _candidate(
    text: str,
    *,
    confidence: Confidence = Confidence.MEDIUM,
    ttl_policy: str = "review",
) -> MemoryCandidate:
    return MemoryCandidate(
        text=text,
        kind=MemoryKind.NOTE,
        confidence=confidence,
        source_refs=(
            SourceRef(
                source_type="manual",
                source_id="semantic-dedupe-test",
                quote_preview=text,
            ),
        ),
        safe_reason="semantic dedupe test",
        operation_hint=CandidateOperation.ADD,
        tags=("test",),
        ttl_policy=ttl_policy,
    )


def _consolidate(
    client: TestClient,
    *,
    capture_id: str,
    extractor: StaticExtractor,
    auto_apply_safe_enabled: bool,
):
    container = client.app.state.container
    use_case = ConsolidateCaptureUseCase(
        uow_factory=container.uow_factory,
        clock=container.clock,
        ids=container.ids,
        extractor=extractor,
        auto_apply_safe_enabled=auto_apply_safe_enabled,
    )
    return asyncio.run(use_case.execute(ConsolidateCaptureCommand(capture_id=capture_id)))


def _list_facts(client: TestClient, *, headers: dict[str, str], space_slug: str):
    return client.get(
        "/v1/facts",
        params={
            "space_slug": space_slug,
            "profile_external_ref": "default",
            "status": "active",
        },
        headers=headers,
    )


def _list_suggestions(client: TestClient, *, headers: dict[str, str], space_slug: str):
    return client.get(
        "/v1/suggestions",
        params={
            "space_slug": space_slug,
            "profile_external_ref": "default",
            "status": "pending",
        },
        headers=headers,
    )
