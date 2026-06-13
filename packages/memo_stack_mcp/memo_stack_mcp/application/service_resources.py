"""Read-only MCP resource rendering for MemoryToolService."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from memo_stack_mcp.application.service_helpers import (
    bounded_resource_value,
    generated_at,
    payload_items,
    resource_json,
)
from memo_stack_mcp.domain.models import (
    MemoryScope,
    has_control_characters,
    has_zero_width_characters,
)


class MemoryToolResourceMixin:
    async def resource_status(self) -> str:
        return resource_json(await self.status())

    async def resource_scope_summary(
        self, *, space_slug: str, memory_scope_external_ref: str
    ) -> str:
        scope = self._resource_scope(space_slug, memory_scope_external_ref)
        facts = await self._gateway.list_facts(scope=scope, status="active", limit=10, cursor=None)
        suggestions = await self._gateway.list_suggestions(
            scope=scope,
            status="pending",
            operation=None,
            category=None,
            tag=None,
            limit=10,
        )
        active_facts, facts_truncated = bounded_resource_value(
            payload_items(facts),
            max_string_chars=self._settings.max_tool_text_chars,
        )
        pending_suggestions, suggestions_truncated = bounded_resource_value(
            payload_items(suggestions),
            max_string_chars=self._settings.max_tool_text_chars,
        )
        return resource_json(
            {
                "resource_type": "scope_summary",
                "generated_at": generated_at(),
                "scope": asdict(scope),
                "active_facts_preview": active_facts,
                "pending_suggestions_preview": pending_suggestions,
                "truncated": facts_truncated or suggestions_truncated,
                "evidence_only": True,
            }
        )

    async def resource_scope_facts(self, *, space_slug: str, memory_scope_external_ref: str) -> str:
        scope = self._resource_scope(space_slug, memory_scope_external_ref)
        payload = await self._gateway.list_facts(
            scope=scope,
            status="active",
            limit=50,
            cursor=None,
        )
        facts, truncated = bounded_resource_value(
            payload_items(payload),
            max_string_chars=self._settings.max_tool_text_chars,
        )
        return resource_json(
            {
                "resource_type": "scope_facts",
                "generated_at": generated_at(),
                "scope": asdict(scope),
                "facts": facts,
                "truncated": truncated,
                "evidence_only": True,
            }
        )

    async def resource_scope_suggestions(
        self,
        *,
        space_slug: str,
        memory_scope_external_ref: str,
    ) -> str:
        scope = self._resource_scope(space_slug, memory_scope_external_ref)
        payload = await self._gateway.list_suggestions(
            scope=scope,
            status="pending",
            operation=None,
            category=None,
            tag=None,
            limit=50,
        )
        suggestions, truncated = bounded_resource_value(
            payload_items(payload),
            max_string_chars=self._settings.max_tool_text_chars,
        )
        return resource_json(
            {
                "resource_type": "scope_suggestions",
                "generated_at": generated_at(),
                "scope": asdict(scope),
                "suggestions": suggestions,
                "truncated": truncated,
                "evidence_only": True,
            }
        )

    async def resource_fact(self, *, fact_id: str) -> str:
        safe_fact_id = self._resource_arg("fact_id", fact_id)
        payload = await self._gateway.get_fact(fact_id=safe_fact_id)
        fact, truncated = bounded_resource_value(
            payload.get("data", payload),
            max_string_chars=self._settings.max_tool_text_chars,
        )
        return resource_json(
            {
                "resource_type": "fact",
                "generated_at": generated_at(),
                "fact": fact,
                "truncated": truncated,
                "evidence_only": True,
            }
        )

    async def resource_fact_versions(self, *, fact_id: str) -> str:
        safe_fact_id = self._resource_arg("fact_id", fact_id)
        payload = await self._gateway.list_fact_versions(fact_id=safe_fact_id)
        versions, truncated = bounded_resource_value(
            payload.get("data", payload),
            max_string_chars=self._settings.max_tool_text_chars,
        )
        return resource_json(
            {
                "resource_type": "fact_versions",
                "generated_at": generated_at(),
                "versions": versions,
                "truncated": truncated,
                "evidence_only": True,
            }
        )

    def _with_search_resource_links(self, data: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(data)
        resource_uris: list[str] = []
        for key in ("items", "facts", "chunks"):
            raw_items = normalized.get(key)
            if not isinstance(raw_items, list):
                continue
            linked_items: list[dict[str, Any]] = []
            for raw_item in raw_items:
                if not isinstance(raw_item, dict):
                    continue
                item = dict(raw_item)
                fact_id = str(item.get("fact_id") or item.get("id") or item.get("item_id") or "")
                item_type = str(item.get("item_type") or item.get("type") or "")
                if fact_id and (not item_type or item_type == "fact"):
                    item.setdefault("resource_uri", f"memory://fact/{fact_id}")
                    resource_uris.append(str(item["resource_uri"]))
                    item.setdefault("item_type", "fact")
                    item.setdefault("item_id", fact_id)
                linked_items.append(item)
            normalized[key] = linked_items
        if resource_uris:
            normalized.setdefault("resource_uris", sorted(set(resource_uris)))
        return normalized

    def _resource_scope(self, space_slug: str, memory_scope_external_ref: str) -> MemoryScope:
        return MemoryScope(
            space_slug=self._resource_arg("space_slug", space_slug),
            memory_scope_external_ref=self._resource_arg(
                "memory_scope_external_ref", memory_scope_external_ref
            ),
        )

    def _resource_arg(self, field_name: str, value: str) -> str:
        safe_value = value.strip()
        if not safe_value:
            raise ValueError(f"{field_name} is required")
        if safe_value in {".", ".."}:
            raise ValueError(f"{field_name} is invalid")
        if "%" in safe_value:
            raise ValueError(f"{field_name} cannot contain percent encoding")
        if "/" in safe_value or "\\" in safe_value:
            raise ValueError(f"{field_name} cannot contain path separators")
        if ":" in safe_value:
            raise ValueError(f"{field_name} cannot contain nested URI syntax")
        if has_control_characters(safe_value) or has_zero_width_characters(safe_value):
            raise ValueError(f"{field_name} contains unsafe formatting characters")
        return safe_value
