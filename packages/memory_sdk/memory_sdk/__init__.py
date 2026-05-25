"""Small HTTP SDK for Memory Platform Core Lite."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class MemoryPlatformError(RuntimeError):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        retryable: bool,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class MemoryPlatformClient:
    base_url: str = "http://127.0.0.1:7788"
    token: str | None = None
    timeout: float = 10.0
    transport: httpx.BaseTransport | None = None

    def create_space(self, *, slug: str, name: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/spaces",
            json={"slug": slug, "name": name},
        )

    def list_spaces(self) -> dict[str, Any]:
        return self._request("GET", "/v1/spaces")

    def create_profile(
        self,
        *,
        space_id: str,
        external_ref: str,
        name: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/profiles",
            json={
                "space_id": space_id,
                "external_ref": external_ref,
                "name": name,
            },
        )

    def list_profiles(self, *, space_id: str) -> dict[str, Any]:
        return self._request("GET", "/v1/profiles", params={"space_id": space_id})

    def remember_fact(
        self,
        *,
        space_id: str | None = None,
        profile_id: str | None = None,
        text: str,
        source_refs: list[dict[str, Any]],
        kind: str = "note",
        thread_id: str | None = None,
        space_slug: str | None = None,
        profile_external_ref: str | None = None,
        thread_external_ref: str | None = None,
        idempotency_key: str | None = None,
        classification: str = "internal",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/facts",
            json=_without_none(
                {
                    "space_id": space_id,
                    "profile_id": profile_id,
                    "thread_id": thread_id,
                    "space_slug": space_slug,
                    "profile_external_ref": profile_external_ref,
                    "thread_external_ref": thread_external_ref,
                    "text": text,
                    "kind": kind,
                    "source_refs": source_refs,
                    "classification": classification,
                }
            ),
            idempotency_key=idempotency_key,
        )

    def update_fact(
        self,
        fact_id: str,
        *,
        expected_version: int,
        text: str,
        reason: str,
        source_refs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/v1/facts/{fact_id}",
            json={
                "expected_version": expected_version,
                "text": text,
                "reason": reason,
                "source_refs": source_refs,
            },
        )

    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/v1/facts/{fact_id}")

    def get_fact(self, fact_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/facts/{fact_id}")

    def list_fact_versions(self, fact_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/facts/{fact_id}/versions")

    def list_facts(
        self,
        *,
        space_id: str | None = None,
        profile_id: str | None = None,
        space_slug: str | None = None,
        profile_external_ref: str | None = None,
        thread_id: str | None = None,
        thread_external_ref: str | None = None,
        status: str | None = "active",
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params = _without_none(
            {
                "space_id": space_id,
                "profile_id": profile_id,
                "space_slug": space_slug,
                "profile_external_ref": profile_external_ref,
                "thread_id": thread_id,
                "thread_external_ref": thread_external_ref,
                "limit": limit,
            }
        )
        if status is not None:
            params["status"] = status
        if cursor is not None:
            params["cursor"] = cursor
        return self._request("GET", "/v1/facts", params=params)

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/v1/health")

    def capabilities(self) -> dict[str, Any]:
        return self._request("GET", "/v1/capabilities")

    def diagnostics_adapters(self) -> dict[str, Any]:
        return self._request("GET", "/v1/diagnostics/adapters")

    def diagnostics_outbox(
        self,
        *,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        return self._request("GET", "/v1/diagnostics/outbox", params=params)

    def diagnostics_profile(self, profile_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/diagnostics/profile/{profile_id}")

    def ingest_document(
        self,
        *,
        space_id: str | None = None,
        profile_id: str | None = None,
        title: str,
        text: str,
        source_external_id: str,
        source_type: str = "document",
        thread_id: str | None = None,
        space_slug: str | None = None,
        profile_external_ref: str | None = None,
        thread_external_ref: str | None = None,
        idempotency_key: str | None = None,
        classification: str = "unknown",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/documents",
            json=_without_none(
                {
                    "space_id": space_id,
                    "profile_id": profile_id,
                    "thread_id": thread_id,
                    "space_slug": space_slug,
                    "profile_external_ref": profile_external_ref,
                    "thread_external_ref": thread_external_ref,
                    "title": title,
                    "text": text,
                    "source_type": source_type,
                    "source_external_id": source_external_id,
                    "classification": classification,
                }
            ),
            idempotency_key=idempotency_key,
        )

    def ingest_episode(
        self,
        *,
        source_external_id: str,
        text: str,
        source_type: str = "unknown",
        space_id: str | None = None,
        profile_id: str | None = None,
        thread_id: str | None = None,
        space_slug: str | None = None,
        profile_external_ref: str | None = None,
        thread_external_ref: str | None = None,
        occurred_at: str | None = None,
        speaker: str | None = None,
        trust_level: str = "medium",
        kind_hint: str | None = None,
        language: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/episodes",
            json=_without_none(
                {
                    "space_id": space_id,
                    "profile_id": profile_id,
                    "thread_id": thread_id,
                    "space_slug": space_slug,
                    "profile_external_ref": profile_external_ref,
                    "thread_external_ref": thread_external_ref,
                    "source_type": source_type,
                    "source_external_id": source_external_id,
                    "text": text,
                    "occurred_at": occurred_at,
                    "speaker": speaker,
                    "trust_level": trust_level,
                    "kind_hint": kind_hint,
                    "language": language,
                    "metadata": metadata,
                    "idempotency_key": idempotency_key,
                }
            ),
        )

    def get_document(self, document_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/documents/{document_id}")

    def list_document_chunks(
        self,
        document_id: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        return self._request("GET", f"/v1/documents/{document_id}/chunks", params=params)

    def process_document(
        self,
        document_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/documents/{document_id}/process",
            idempotency_key=idempotency_key,
        )

    def delete_document(self, document_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/v1/documents/{document_id}")

    def build_context(
        self,
        *,
        query: str,
        space_id: str | None = None,
        profile_ids: list[str] | None = None,
        thread_id: str | None = None,
        space_slug: str | None = None,
        profile_external_ref: str | None = None,
        profile_external_refs: list[str] | None = None,
        thread_external_ref: str | None = None,
        token_budget: int = 1800,
        max_facts: int = 20,
        max_chunks: int = 30,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/context",
            json=_context_scope_body(
                space_id=space_id,
                profile_ids=profile_ids,
                thread_id=thread_id,
                space_slug=space_slug,
                profile_external_ref=profile_external_ref,
                profile_external_refs=profile_external_refs,
                thread_external_ref=thread_external_ref,
                query=query,
                token_budget=token_budget,
                max_facts=max_facts,
                max_chunks=max_chunks,
            ),
        )

    def search(
        self,
        *,
        query: str,
        space_id: str | None = None,
        profile_ids: list[str] | None = None,
        thread_id: str | None = None,
        space_slug: str | None = None,
        profile_external_ref: str | None = None,
        profile_external_refs: list[str] | None = None,
        thread_external_ref: str | None = None,
        token_budget: int = 1800,
        max_facts: int = 20,
        max_chunks: int = 30,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/search",
            json=_context_scope_body(
                space_id=space_id,
                profile_ids=profile_ids,
                thread_id=thread_id,
                space_slug=space_slug,
                profile_external_ref=profile_external_ref,
                profile_external_refs=profile_external_refs,
                thread_external_ref=thread_external_ref,
                query=query,
                token_budget=token_budget,
                max_facts=max_facts,
                max_chunks=max_chunks,
            ),
        )

    def thread_memory_status(
        self,
        *,
        space_id: str | None = None,
        profile_id: str | None = None,
        thread_id: str | None = None,
        space_slug: str | None = None,
        profile_external_ref: str | None = None,
        thread_external_ref: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/thread-memory/status",
            json=_single_scope_body(
                space_id=space_id,
                profile_id=profile_id,
                thread_id=thread_id,
                space_slug=space_slug,
                profile_external_ref=profile_external_ref,
                thread_external_ref=thread_external_ref,
            ),
        )

    def delete_thread_memory(
        self,
        *,
        space_id: str | None = None,
        profile_id: str | None = None,
        thread_id: str | None = None,
        space_slug: str | None = None,
        profile_external_ref: str | None = None,
        thread_external_ref: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "DELETE",
            "/v1/thread-memory",
            json=_single_scope_body(
                space_id=space_id,
                profile_id=profile_id,
                thread_id=thread_id,
                space_slug=space_slug,
                profile_external_ref=profile_external_ref,
                thread_external_ref=thread_external_ref,
            ),
        )

    def create_suggestion(
        self,
        *,
        space_id: str,
        profile_id: str,
        candidate_text: str,
        safe_reason: str,
        kind: str = "note",
        source_refs: list[dict[str, Any]] | None = None,
        trust_level: str = "medium",
        confidence: str = "medium",
        target_fact_id: str | None = None,
        target_fact_version: int | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/suggestions",
            json={
                "space_id": space_id,
                "profile_id": profile_id,
                "candidate_text": candidate_text,
                "safe_reason": safe_reason,
                "kind": kind,
                "source_refs": source_refs or [],
                "trust_level": trust_level,
                "confidence": confidence,
                "target_fact_id": target_fact_id,
                "target_fact_version": target_fact_version,
            },
        )

    def list_suggestions(
        self,
        *,
        space_id: str,
        profile_id: str,
        status: str | None = None,
    ) -> dict[str, Any]:
        params = {
            "space_id": space_id,
            "profile_id": profile_id,
        }
        if status is not None:
            params["status"] = status
        return self._request("GET", "/v1/suggestions", params=params)

    def approve_suggestion(
        self,
        suggestion_id: str,
        *,
        reason: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/suggestions/{suggestion_id}/approve",
            json={"reason": reason, "force": force},
        )

    def reject_suggestion(self, suggestion_id: str, *, reason: str | None = None) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/suggestions/{suggestion_id}/reject",
            json={"reason": reason},
        )

    def expire_suggestion(self, suggestion_id: str, *, reason: str | None = None) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/suggestions/{suggestion_id}/expire",
            json={"reason": reason},
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        with httpx.Client(
            base_url=self.base_url.rstrip("/"),
            timeout=self.timeout,
            headers=headers,
            transport=self.transport,
        ) as client:
            try:
                response = client.request(method, path, json=json, params=params)
            except httpx.TransportError as exc:
                raise MemoryPlatformError(
                    status_code=0,
                    code="memory.network_error",
                    message="Memory Platform request failed",
                    retryable=True,
                ) from exc
            if response.is_error:
                raise _to_error(response)
            return response.json()


def _to_error(response: httpx.Response) -> MemoryPlatformError:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    detail = payload.get("detail", {}) if isinstance(payload, dict) else {}
    code = str(error.get("code") or detail.get("code") or "memory.http_error")
    message = str(error.get("message") or response.text or code)
    retryable = bool(error.get("retryable", response.status_code >= 500))
    return MemoryPlatformError(
        status_code=response.status_code,
        code=code,
        message=message,
        retryable=retryable,
    )


def _without_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _single_scope_body(
    *,
    space_id: str | None,
    profile_id: str | None,
    thread_id: str | None,
    space_slug: str | None,
    profile_external_ref: str | None,
    thread_external_ref: str | None,
) -> dict[str, Any]:
    return _without_none(
        {
            "space_id": space_id,
            "profile_id": profile_id,
            "thread_id": thread_id,
            "space_slug": space_slug,
            "profile_external_ref": profile_external_ref,
            "thread_external_ref": thread_external_ref,
        }
    )


def _context_scope_body(
    *,
    space_id: str | None,
    profile_ids: list[str] | None,
    thread_id: str | None,
    space_slug: str | None,
    profile_external_ref: str | None,
    profile_external_refs: list[str] | None,
    thread_external_ref: str | None,
    query: str,
    token_budget: int,
    max_facts: int,
    max_chunks: int,
) -> dict[str, Any]:
    return _without_none(
        {
            "space_id": space_id,
            "profile_ids": profile_ids,
            "thread_id": thread_id,
            "space_slug": space_slug,
            "profile_external_ref": profile_external_ref,
            "profile_external_refs": profile_external_refs,
            "thread_external_ref": thread_external_ref,
            "query": query,
            "token_budget": token_budget,
            "max_facts": max_facts,
            "max_chunks": max_chunks,
        }
    )


__all__ = ["MemoryPlatformClient", "MemoryPlatformError"]
