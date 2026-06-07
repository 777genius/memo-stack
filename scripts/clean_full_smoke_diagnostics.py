"""Safe diagnostics renderers for clean full-provider smoke reports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def context_diagnostic_int(context: Mapping[str, Any], key: str) -> int:
    diagnostics = context.get("diagnostics", {})
    if not isinstance(diagnostics, Mapping):
        return 0
    value = diagnostics.get(key)
    return value if isinstance(value, int) else 0


def safe_context_diagnostics(context: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = context.get("diagnostics", {})
    if not isinstance(diagnostics, Mapping):
        return {}
    allowed_keys = {
        "facts_considered",
        "graph_candidate_count",
        "graph_hydrated_count",
        "graph_status",
        "items_considered",
        "items_used",
        "keyword_chunks_considered",
        "rag_status",
        "stale_graph_drop_count",
        "stale_vector_drop_count",
        "vector_candidate_count",
        "vector_hydrated_count",
        "vector_status",
    }
    return {key: diagnostics[key] for key in allowed_keys if key in diagnostics}


def search_diagnostic_status(search: Mapping[str, Any], key: str) -> str:
    diagnostics = _search_diagnostics(search)
    if not isinstance(diagnostics, Mapping):
        return ""
    return str(diagnostics.get(key) or "")


def search_diagnostic_int(search: Mapping[str, Any], key: str) -> int:
    diagnostics = _search_diagnostics(search)
    if not isinstance(diagnostics, Mapping):
        return 0
    value = diagnostics.get(key)
    return value if isinstance(value, int) else 0


def safe_search_diagnostics(search: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = _search_diagnostics(search)
    if not isinstance(diagnostics, Mapping):
        return {}
    allowed_keys = {
        "facts_considered",
        "graph_candidate_count",
        "graph_hydrated_count",
        "graph_status",
        "keyword_chunks_considered",
        "rag_status",
        "stale_graph_drop_count",
        "stale_vector_drop_count",
        "vector_candidate_count",
        "vector_hydrated_count",
        "vector_status",
    }
    return {key: diagnostics[key] for key in allowed_keys if key in diagnostics}


def safe_status_readiness(status: Mapping[str, Any]) -> dict[str, Any]:
    data = status.get("data", {})
    if not isinstance(data, Mapping):
        return {}
    readiness = data.get("readiness", {})
    if not isinstance(readiness, Mapping):
        return {}
    allowed_keys = {
        "api_reachable",
        "delete_ready",
        "projection_ready",
        "read_ready",
        "write_ready",
    }
    safe = {key: readiness[key] for key in allowed_keys if key in readiness}
    degraded_reasons = readiness.get("degraded_reasons")
    if isinstance(degraded_reasons, list):
        safe["degraded_reasons"] = [
            str(reason) for reason in degraded_reasons if isinstance(reason, str)
        ][:20]
    return safe


def safe_status_adapters(status: Mapping[str, Any]) -> dict[str, Any]:
    capabilities = mcp_status_capabilities(status)
    if not isinstance(capabilities, Mapping):
        return {}
    adapters = capabilities.get("adapters", {})
    result = adapter_map_status(adapters) if isinstance(adapters, Mapping) else {}
    capability_items = capabilities.get("capabilities", [])
    if isinstance(capability_items, list):
        for item in capability_items:
            if not isinstance(item, Mapping):
                continue
            name = item.get("adapter_name")
            if not isinstance(name, str) or name in result:
                continue
            result[name] = {
                key: item[key] for key in ("enabled", "healthy", "status") if key in item
            }
    return result


def required_mcp_adapters_ready(status: Mapping[str, Any], names: tuple[str, ...]) -> bool:
    return all(mcp_adapter_ready(status, name) for name in names)


def mcp_adapter_ready(status: Mapping[str, Any], name: str) -> bool:
    capabilities = mcp_status_capabilities(status)
    if not isinstance(capabilities, Mapping):
        return False
    adapters = capabilities.get("adapters", {})
    if isinstance(adapters, Mapping):
        adapter = adapters.get(name)
        if isinstance(adapter, Mapping):
            return adapter_status_ready(adapter)
    capability_items = capabilities.get("capabilities", [])
    if not isinstance(capability_items, list):
        return False
    return any(
        adapter_status_ready(item)
        for item in capability_items
        if isinstance(item, Mapping) and item.get("adapter_name") == name
    )


def mcp_status_capabilities(status: Mapping[str, Any]) -> Mapping[str, Any] | None:
    data = status.get("data", {})
    if not isinstance(data, Mapping):
        return None
    capabilities = data.get("capabilities", {})
    if not isinstance(capabilities, Mapping):
        return None
    return capabilities


def adapter_map_status(adapters: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, adapter in adapters.items():
        if isinstance(adapter, Mapping):
            result[str(name)] = {
                key: adapter[key] for key in ("enabled", "healthy", "status") if key in adapter
            }
    return result


def adapter_status_ready(adapter: Mapping[str, Any]) -> bool:
    status = str(adapter.get("status") or "")
    healthy = bool(adapter.get("healthy", status in {"ok", "healthy"}))
    return adapter.get("enabled") is True and healthy and status in {"", "ok", "healthy"}


def _search_diagnostics(search: Mapping[str, Any]) -> Mapping[str, Any] | None:
    data = search.get("data", {})
    if not isinstance(data, Mapping):
        return None
    diagnostics = data.get("diagnostics", {})
    if not isinstance(diagnostics, Mapping):
        return None
    return diagnostics
