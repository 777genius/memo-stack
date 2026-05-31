"""HTTP adapter from MCP tools to the Memory Platform API."""

from __future__ import annotations

from typing import Any

import httpx

from memory_mcp.domain.models import MemoryGatewayError, MemoryReadScope, MemoryScope, SourceRef


class HttpMemoryGateway:
    def __init__(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth_token = auth_token
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/v1/health")

    async def capabilities(self) -> dict[str, Any]:
        return await self._request("GET", "/v1/capabilities")

    async def build_context(
        self,
        *,
        scope: MemoryReadScope,
        query: str,
        token_budget: int,
        max_facts: int,
        max_chunks: int,
    ) -> dict[str, Any]:
        profile_payload = _read_scope_profile_payload(scope)
        return await self._request(
            "POST",
            "/v1/context",
            json=_without_none(
                {
                    "space_slug": scope.space_slug,
                    **profile_payload,
                    "thread_external_ref": scope.thread_external_ref,
                    "query": query,
                    "token_budget": token_budget,
                    "max_facts": max_facts,
                    "max_chunks": max_chunks,
                }
            ),
        )

    async def remember_fact(
        self,
        *,
        scope: MemoryScope,
        text: str,
        kind: str,
        source_refs: list[SourceRef],
        classification: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/facts",
            json=_without_none(
                {
                    "space_slug": scope.space_slug,
                    "profile_external_ref": scope.profile_external_ref,
                    "thread_external_ref": scope.thread_external_ref,
                    "text": text,
                    "kind": kind,
                    "source_refs": [source.to_payload() for source in source_refs],
                    "classification": classification,
                }
            ),
            idempotency_key=idempotency_key,
        )

    async def list_facts(
        self,
        *,
        scope: MemoryScope,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/v1/facts",
            params=_without_none(
                {
                    "space_slug": scope.space_slug,
                    "profile_external_ref": scope.profile_external_ref,
                    "status": status,
                    "limit": limit,
                    "cursor": cursor,
                }
            ),
        )

    async def get_fact(self, *, fact_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v1/facts/{fact_id}")

    async def list_fact_versions(self, *, fact_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v1/facts/{fact_id}/versions")

    async def update_fact(
        self,
        *,
        fact_id: str,
        expected_version: int,
        text: str,
        reason: str,
        source_refs: list[SourceRef],
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/v1/facts/{fact_id}",
            json={
                "expected_version": expected_version,
                "text": text,
                "reason": reason,
                "source_refs": [source.to_payload() for source in source_refs],
            },
        )

    async def forget_fact(self, *, fact_id: str) -> dict[str, Any]:
        return await self._request("DELETE", f"/v1/facts/{fact_id}")

    async def create_suggestion(
        self,
        *,
        scope: MemoryScope,
        candidate_text: str,
        kind: str,
        source_refs: list[SourceRef],
        confidence: str,
        trust_level: str,
        safe_reason: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/suggestions",
            json=_without_none(
                {
                    "space_slug": scope.space_slug,
                    "profile_external_ref": scope.profile_external_ref,
                    "candidate_text": candidate_text,
                    "kind": kind,
                    "source_refs": [source.to_payload() for source in source_refs],
                    "confidence": confidence,
                    "trust_level": trust_level,
                    "safe_reason": safe_reason,
                }
            ),
        )

    async def list_suggestions(
        self,
        *,
        scope: MemoryScope,
        status: str | None,
        limit: int,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/v1/suggestions",
            params=_without_none(
                {
                    "space_slug": scope.space_slug,
                    "profile_external_ref": scope.profile_external_ref,
                    "status": status,
                    "limit": limit,
                }
            ),
        )

    async def approve_suggestion(
        self,
        *,
        suggestion_id: str,
        reason: str | None,
        force: bool,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/suggestions/{suggestion_id}/approve",
            json=_without_none({"reason": reason, "force": force}),
        )

    async def reject_suggestion(
        self,
        *,
        suggestion_id: str,
        reason: str | None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/suggestions/{suggestion_id}/reject",
            json=_without_none({"reason": reason}),
        )

    async def expire_suggestion(
        self,
        *,
        suggestion_id: str,
        reason: str | None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/suggestions/{suggestion_id}/expire",
            json=_without_none({"reason": reason}),
        )

    async def ingest_document(
        self,
        *,
        scope: MemoryScope,
        title: str,
        text: str,
        source_type: str,
        source_external_id: str,
        classification: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/documents",
            json=_without_none(
                {
                    "space_slug": scope.space_slug,
                    "profile_external_ref": scope.profile_external_ref,
                    "thread_external_ref": scope.thread_external_ref,
                    "title": title,
                    "text": text,
                    "source_type": source_type,
                    "source_external_id": source_external_id,
                    "classification": classification,
                }
            ),
            idempotency_key=idempotency_key,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
            headers=headers,
            transport=self._transport,
        ) as client:
            try:
                response = await client.request(method, path, json=json, params=params)
            except httpx.TransportError as exc:
                raise MemoryGatewayError(
                    status_code=0,
                    code="memory_mcp.network_error",
                    message="Memory Platform HTTP request failed",
                    retryable=True,
                ) from exc
        if response.is_error:
            raise _to_error(response)
        try:
            return response.json()
        except ValueError as exc:
            raise MemoryGatewayError(
                status_code=response.status_code,
                code="memory_mcp.invalid_json",
                message="Memory Platform returned invalid JSON",
                retryable=False,
            ) from exc


def _to_error(response: httpx.Response) -> MemoryGatewayError:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    detail = payload.get("detail", {}) if isinstance(payload, dict) else {}
    code = str(error.get("code") or detail.get("code") or "memory_mcp.http_error")
    message = str(error.get("message") or detail.get("message") or response.text or code)
    retryable = bool(error.get("retryable", response.status_code >= 500))
    return MemoryGatewayError(
        status_code=response.status_code,
        code=code,
        message=message,
        retryable=retryable,
    )


def _without_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _read_scope_profile_payload(scope: MemoryReadScope) -> dict[str, Any]:
    if len(scope.profile_external_refs) == 1:
        return {"profile_external_ref": scope.profile_external_refs[0]}
    return {"profile_external_refs": list(scope.profile_external_refs)}
