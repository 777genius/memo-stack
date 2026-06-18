"""Scope and source-reference helpers for MemoryToolService."""

from __future__ import annotations

from infinity_context_mcp.application.service_constants import SOURCE_TYPES
from infinity_context_mcp.application.service_helpers import stable_key
from infinity_context_mcp.domain.models import (
    MemoryGatewayError,
    MemoryReadScope,
    MemoryScope,
    SourceRef,
    contains_sensitive_value,
    has_control_characters,
    has_zero_width_characters,
    safe_message,
)


class MemoryToolScopeMixin:
    def _default_scope(self) -> MemoryScope:
        return MemoryScope(
            space_slug=self._settings.default_space_slug,
            memory_scope_external_ref=self._settings.default_memory_scope_external_ref,
            thread_external_ref=self._settings.default_thread_external_ref,
        )

    def _scope(
        self,
        space_slug: str | None,
        memory_scope_external_ref: str | None,
        thread_external_ref: str | None,
    ) -> MemoryScope:
        return MemoryScope(
            space_slug=(space_slug or self._settings.default_space_slug).strip(),
            memory_scope_external_ref=(
                memory_scope_external_ref or self._settings.default_memory_scope_external_ref
            ).strip(),
            thread_external_ref=thread_external_ref or self._settings.default_thread_external_ref,
        )

    def _read_scope(
        self,
        *,
        space_slug: str | None,
        memory_scope_external_ref: str | None,
        memory_scope_external_refs: list[str] | None,
        thread_external_ref: str | None,
    ) -> MemoryReadScope:
        refs: list[str] = []
        if memory_scope_external_ref:
            refs.append(memory_scope_external_ref)
        refs.extend(memory_scope_external_refs or [])
        if not refs:
            refs.append(self._settings.default_memory_scope_external_ref)
        try:
            return MemoryReadScope(
                space_slug=(space_slug or self._settings.default_space_slug).strip(),
                memory_scope_external_refs=tuple(refs),
                thread_external_ref=(
                    thread_external_ref or self._settings.default_thread_external_ref
                ),
            )
        except ValueError as exc:
            raise MemoryGatewayError(
                status_code=400,
                code="infinity_context_mcp.invalid_scope",
                message=str(exc),
                retryable=False,
            ) from exc

    def _source_ref(
        self,
        *,
        source_type: str | None,
        source_id: str | None,
        quote_preview: str | None,
        fallback_seed: str,
    ) -> SourceRef:
        quote = quote_preview.strip() if quote_preview else None
        if contains_sensitive_value(quote):
            raise MemoryGatewayError(
                status_code=400,
                code="infinity_context_mcp.policy.secret_detected",
                message="Quote preview contains a credential-like value",
                retryable=False,
            )
        try:
            return SourceRef(
                source_type=self._safe_source_type(source_type),
                source_id=self._safe_source_id(
                    source_id or stable_key("mcp-source", fallback_seed)
                ),
                quote_preview=quote,
            )
        except ValueError as exc:
            raise MemoryGatewayError(
                status_code=400,
                code="infinity_context_mcp.validation.invalid_source_ref",
                message=str(exc),
                retryable=False,
            ) from exc

    def _safe_source_type(self, source_type: str | None) -> str:
        value = (source_type or self._settings.source_type).strip()
        if value not in SOURCE_TYPES:
            raise MemoryGatewayError(
                status_code=400,
                code="infinity_context_mcp.validation.invalid_source_ref",
                message=f"Unsupported source_type: {safe_message(value)}",
                retryable=False,
            )
        return value

    def _safe_source_id(self, source_id: str) -> str:
        value = source_id.strip()
        if contains_sensitive_value(value):
            raise MemoryGatewayError(
                status_code=400,
                code="infinity_context_mcp.validation.invalid_source_ref",
                message="Source id contains a credential-like value",
                retryable=False,
            )
        if has_control_characters(value) or has_zero_width_characters(value):
            raise MemoryGatewayError(
                status_code=400,
                code="infinity_context_mcp.validation.invalid_source_ref",
                message="Source id contains unsafe formatting characters",
                retryable=False,
            )
        if value.startswith(("/Users/", "/home/")) or "\\Users\\" in value:
            return stable_key("mcp-source-path", value)
        return value
