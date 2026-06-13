from __future__ import annotations

from typing import Any


class RecordingGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def health(self) -> dict[str, Any]:
        return {"status": "ok"}

    async def capabilities(self) -> dict[str, Any]:
        return {
            "policy_mode": "active_context",
            "capabilities": [
                {
                    "adapter_name": "graphiti",
                    "capability": "temporal_fact_graph",
                    "enabled": True,
                    "healthy": True,
                    "status": "ok",
                    "degraded_reason": None,
                }
            ],
        }

    async def build_context(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("build_context", kwargs))
        return {"data": {"rendered_text": "stored context", "items": []}}

    async def build_digest(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("build_digest", kwargs))
        return {
            "data": {
                "digest_id": "dig_1",
                "topic": kwargs["topic"],
                "rendered_markdown": "# Memory Digest\nEvidence only: true",
                "sections": [],
                "diagnostics": {"evidence_only": True},
            }
        }

    async def export_memory_scope_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("export_memory_scope_snapshot", kwargs))
        return {
            "status": "ok",
            "counts": {"facts": 1, "documents": 0, "chunks": 0, "source_refs": 1},
            "redacted": kwargs["redacted"],
            "data": {
                "schema_version": 1,
                "space": {"slug": kwargs["scope"].space_slug},
                "memory_scope": {"external_ref": kwargs["scope"].memory_scope_external_ref},
                "facts": [{"id": "fact_1", "text": None if kwargs["redacted"] else "fact"}],
                "documents": [],
                "chunks": [],
                "source_refs": [],
                "redacted": kwargs["redacted"],
            },
        }

    async def import_memory_scope_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("import_memory_scope_snapshot", kwargs))
        return {
            "data": {
                "status": "ok",
                "dry_run": kwargs["dry_run"],
                "merge_strategy": kwargs["merge_strategy"],
                "would_import": {"facts": 1, "documents": 0, "chunks": 0, "source_refs": 1},
            }
        }

    async def remember_fact(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("remember_fact", kwargs))
        return {
            "data": {
                "id": "fact_1",
                "version": 1,
                "text": kwargs["text"],
                "source_refs": [source.to_payload() for source in kwargs["source_refs"]],
            }
        }

    async def list_facts(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("list_facts", kwargs))
        return {"data": []}

    async def get_fact(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("get_fact", kwargs))
        return {"data": {"id": kwargs["fact_id"]}}

    async def list_fact_versions(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("list_fact_versions", kwargs))
        return {"data": []}

    async def update_fact(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("update_fact", kwargs))
        return {"data": {"id": kwargs["fact_id"], "version": kwargs["expected_version"] + 1}}

    async def forget_fact(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("forget_fact", kwargs))
        return {"data": {"id": kwargs["fact_id"], "status": "deleted"}}

    async def create_suggestion(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("create_suggestion", kwargs))
        return {
            "data": {
                "id": "sug_1",
                "status": "pending",
                "candidate_text": kwargs["candidate_text"],
            }
        }

    async def list_suggestions(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("list_suggestions", kwargs))
        return {"data": []}

    async def approve_suggestion(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("approve_suggestion", kwargs))
        return {
            "data": {
                "suggestion": {"id": kwargs["suggestion_id"], "status": "approved"},
                "fact": {"id": "fact_from_suggestion", "version": 1},
            }
        }

    async def reject_suggestion(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("reject_suggestion", kwargs))
        return {"data": {"id": kwargs["suggestion_id"], "status": "rejected"}}

    async def expire_suggestion(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("expire_suggestion", kwargs))
        return {"data": {"id": kwargs["suggestion_id"], "status": "expired"}}

    async def list_captures(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("list_captures", kwargs))
        return {
            "data": {
                "items": [
                    {
                        "id": "cap_1",
                        "capture_id": "cap_1",
                        "status": "accepted",
                        "consolidation_status": "pending",
                        "text_preview": "Remember: Postgres is canonical truth.",
                    }
                ]
            }
        }

    async def consolidate_capture(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("consolidate_capture", kwargs))
        return {
            "data": {
                "capture": {
                    "id": kwargs["capture_id"],
                    "capture_id": kwargs["capture_id"],
                    "status": "accepted",
                    "consolidation_status": "consolidated",
                },
                "created_suggestions": 1,
                "suggestion_ids": ["sug_1"],
            }
        }

    async def ingest_document(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("ingest_document", kwargs))
        return {"data": {"id": "doc_1"}}
