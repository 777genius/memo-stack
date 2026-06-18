"""Canonical multimodal artifact evidence retrieval."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from json import JSONDecodeError
from math import isfinite

from infinity_context_core.application.context_relevance import score_query_relevance
from infinity_context_core.application.dto import BuildContextQuery, ContextItem
from infinity_context_core.application.safe_payload import safe_metadata_text
from infinity_context_core.application.sensitive_text import contains_sensitive_text
from infinity_context_core.application.source_refs import source_ref_location_summary
from infinity_context_core.domain.assets import AssetStatus
from infinity_context_core.domain.entities import SourceRef
from infinity_context_core.domain.extraction import ExtractionArtifact, ExtractionArtifactType
from infinity_context_core.ports.assets import BlobStoragePort
from infinity_context_core.ports.unit_of_work import UnitOfWorkFactoryPort

_MEDIA_MANIFEST_SCHEMA_VERSION = "infinity_context.multimodal_manifest.v1"
_MAX_MANIFEST_BYTES = 1_000_000
_MAX_EVIDENCE_TEXT_CHARS = 700
_MAX_QUOTE_PREVIEW_CHARS = 240
_MAX_JOBS_PER_SCOPE = 120
_INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+instructions\b", re.I),
    re.compile(r"\b(system|developer|hidden)\s+(prompt|message|instructions?)\b", re.I),
    re.compile(r"\b(reveal|print|exfiltrate|leak)\s+.*\b(prompt|secret|token|key)\b", re.I),
)
_SECRET_MARKERS = (
    "authorization:",
    "bearer ",
    "api_key",
    "apikey",
    "password=",
    "password:",
    "private_key",
    "secret=",
    "sk-",
    "token=",
    "token:",
)


@dataclass(frozen=True)
class _ManifestCandidate:
    artifact: ExtractionArtifact
    job_id: str
    memory_scope_id: str


class ArtifactEvidenceContextCollector:
    """Collects prompt-safe context items from first-party media manifests."""

    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactoryPort,
        blob_storage: BlobStoragePort | None = None,
        max_manifest_bytes: int = _MAX_MANIFEST_BYTES,
    ) -> None:
        self._uow_factory = uow_factory
        self._blob_storage = blob_storage
        self._max_manifest_bytes = max(1, max_manifest_bytes)

    async def collect(
        self,
        *,
        query: BuildContextQuery,
        memory_scope_ids: tuple[str, ...],
        diagnostics: dict[str, object],
    ) -> tuple[ContextItem, ...]:
        _init_diagnostics(diagnostics)
        if query.max_evidence_items <= 0:
            diagnostics["artifact_evidence_status"] = "skipped"
            return ()
        if self._blob_storage is None:
            diagnostics["artifact_evidence_status"] = "disabled"
            return ()

        manifests = await self._list_candidate_manifests(
            query=query,
            memory_scope_ids=memory_scope_ids,
            diagnostics=diagnostics,
        )
        if not manifests:
            diagnostics["artifact_evidence_status"] = "ok"
            return ()

        items: list[ContextItem] = []
        for candidate in manifests:
            if len(items) >= query.max_evidence_items:
                break
            payload = await self._read_manifest(candidate.artifact, diagnostics=diagnostics)
            if payload is None:
                continue
            diagnostics["artifact_evidence_manifests_used"] = (
                int(diagnostics["artifact_evidence_manifests_used"]) + 1
            )
            for item in _context_items_from_manifest(
                candidate=candidate,
                payload=payload,
                query=query,
                diagnostics=diagnostics,
            ):
                items.append(item)
                if len(items) >= query.max_evidence_items:
                    break
        diagnostics["artifact_evidence_items_used"] = len(items)
        diagnostics["artifact_evidence_status"] = "ok"
        return tuple(items)

    async def _list_candidate_manifests(
        self,
        *,
        query: BuildContextQuery,
        memory_scope_ids: tuple[str, ...],
        diagnostics: dict[str, object],
    ) -> tuple[_ManifestCandidate, ...]:
        job_limit = min(
            _MAX_JOBS_PER_SCOPE,
            max(query.max_evidence_items * 4, query.max_evidence_items),
        )
        manifests: list[_ManifestCandidate] = []
        async with self._uow_factory() as uow:
            for memory_scope_id in memory_scope_ids:
                jobs = await uow.asset_extractions.list_for_scope(
                    space_id=str(query.space_id),
                    memory_scope_id=memory_scope_id,
                    thread_id=str(query.thread_id) if query.thread_id else None,
                    status="succeeded",
                    limit=job_limit,
                )
                diagnostics["artifact_evidence_jobs_considered"] = (
                    int(diagnostics["artifact_evidence_jobs_considered"]) + len(jobs)
                )
                for job in jobs:
                    for artifact in await uow.asset_extractions.list_artifacts(job_id=str(job.id)):
                        if artifact.artifact_type != ExtractionArtifactType.MEDIA_MANIFEST:
                            continue
                        asset = await uow.assets.get_by_id(str(artifact.asset_id))
                        if asset is None or asset.status != AssetStatus.STORED:
                            diagnostics["artifact_evidence_stale_asset_drop_count"] = (
                                int(diagnostics["artifact_evidence_stale_asset_drop_count"]) + 1
                            )
                            continue
                        manifests.append(
                            _ManifestCandidate(
                                artifact=artifact,
                                job_id=str(job.id),
                                memory_scope_id=str(job.memory_scope_id),
                            )
                        )
                        diagnostics["artifact_evidence_manifests_considered"] = (
                            int(diagnostics["artifact_evidence_manifests_considered"]) + 1
                        )
                        if len(manifests) >= job_limit:
                            return tuple(manifests)
        return tuple(manifests)

    async def _read_manifest(
        self,
        artifact: ExtractionArtifact,
        *,
        diagnostics: dict[str, object],
    ) -> Mapping[str, object] | None:
        if artifact.byte_size > self._max_manifest_bytes:
            diagnostics["artifact_evidence_manifest_too_large_count"] = (
                int(diagnostics["artifact_evidence_manifest_too_large_count"]) + 1
            )
            return None
        try:
            content = await self._blob_storage.read_bytes(storage_key=artifact.storage_key)
        except Exception:
            diagnostics["artifact_evidence_read_error_count"] = (
                int(diagnostics["artifact_evidence_read_error_count"]) + 1
            )
            return None
        if len(content) > self._max_manifest_bytes:
            diagnostics["artifact_evidence_manifest_too_large_count"] = (
                int(diagnostics["artifact_evidence_manifest_too_large_count"]) + 1
            )
            return None
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, JSONDecodeError):
            diagnostics["artifact_evidence_parse_error_count"] = (
                int(diagnostics["artifact_evidence_parse_error_count"]) + 1
            )
            return None
        if not isinstance(payload, Mapping):
            diagnostics["artifact_evidence_parse_error_count"] = (
                int(diagnostics["artifact_evidence_parse_error_count"]) + 1
            )
            return None
        if payload.get("schema_version") != _MEDIA_MANIFEST_SCHEMA_VERSION:
            diagnostics["artifact_evidence_schema_skip_count"] = (
                int(diagnostics["artifact_evidence_schema_skip_count"]) + 1
            )
            return None
        return payload


def _context_items_from_manifest(
    *,
    candidate: _ManifestCandidate,
    payload: Mapping[str, object],
    query: BuildContextQuery,
    diagnostics: dict[str, object],
) -> tuple[ContextItem, ...]:
    evidence_items = payload.get("evidence_items")
    if not isinstance(evidence_items, list):
        return ()
    items: list[ContextItem] = []
    for index, raw_item in enumerate(evidence_items):
        if not isinstance(raw_item, Mapping):
            continue
        diagnostics["artifact_evidence_items_considered"] = (
            int(diagnostics["artifact_evidence_items_considered"]) + 1
        )
        raw_text = str(raw_item.get("text_preview") or "")
        text = safe_metadata_text(raw_text, limit=_MAX_EVIDENCE_TEXT_CHARS)
        if not text.strip():
            continue
        if _looks_sensitive(raw_text):
            diagnostics["artifact_evidence_sensitive_drop_count"] = (
                int(diagnostics["artifact_evidence_sensitive_drop_count"]) + 1
            )
            continue
        if _looks_like_prompt_injection(text):
            diagnostics["artifact_evidence_prompt_injection_drop_count"] = (
                int(diagnostics["artifact_evidence_prompt_injection_drop_count"]) + 1
            )
            continue
        relevance = score_query_relevance(
            query=query.query,
            text=" ".join(
                (
                    text,
                    str(raw_item.get("kind") or ""),
                    str(raw_item.get("modality") or ""),
                )
            ),
        )
        if relevance.query_term_count > 0 and relevance.unique_term_hits <= 0:
            diagnostics["artifact_evidence_query_drop_count"] = (
                int(diagnostics["artifact_evidence_query_drop_count"]) + 1
            )
            continue
        artifact = candidate.artifact
        source_ref = _source_ref(artifact=artifact, raw_item=raw_item, index=index, text=text)
        score = min(0.86, round(0.7 + relevance.score_boost, 4))
        items.append(
            ContextItem(
                item_id=f"{artifact.id}:{_safe_evidence_id(raw_item, index=index)}",
                item_type="extraction_artifact",
                text=text,
                score=score,
                source_refs=(source_ref,),
                diagnostics={
                    "memory_scope_id": candidate.memory_scope_id,
                    "retrieval_source": "artifact_evidence",
                    "retrieval_sources": ["artifact_evidence"],
                    "ranking_reason": "matched first-party multimodal extraction evidence",
                    "score_signals": {
                        "base_score": 0.7,
                        "final_score": score,
                        "retrieval_channel": "artifact_evidence",
                        "query_term_count": relevance.query_term_count,
                        "unique_term_hits": relevance.unique_term_hits,
                        "capped_frequency_hits": relevance.capped_frequency_hits,
                        "hit_ratio": relevance.hit_ratio,
                        "query_relevance_boost": relevance.score_boost,
                    },
                    "provenance": {
                        "retrieval_sources": ["artifact_evidence"],
                        "source_ref_count": 1,
                        "artifact_id": str(artifact.id),
                        "asset_id": str(artifact.asset_id),
                        "job_id": candidate.job_id,
                        "artifact_type": artifact.artifact_type.value,
                        "manifest_schema_version": _MEDIA_MANIFEST_SCHEMA_VERSION,
                        "evidence_kind": safe_metadata_text(str(raw_item.get("kind") or "unknown")),
                        "evidence_modality": safe_metadata_text(
                            str(raw_item.get("modality") or "unknown")
                        ),
                        **source_ref_location_summary((source_ref,)),
                    },
                    "artifact_id": str(artifact.id),
                    "asset_id": str(artifact.asset_id),
                    "evidence_kind": safe_metadata_text(str(raw_item.get("kind") or "unknown")),
                    "evidence_modality": safe_metadata_text(
                        str(raw_item.get("modality") or "unknown")
                    ),
                    **source_ref_location_summary((source_ref,)),
                },
            )
        )
    return tuple(items)


def _source_ref(
    *,
    artifact: ExtractionArtifact,
    raw_item: Mapping[str, object],
    index: int,
    text: str,
) -> SourceRef:
    return SourceRef(
        source_type="extraction_artifact",
        source_id=str(artifact.id),
        chunk_id=_safe_evidence_id(raw_item, index=index),
        quote_preview=safe_metadata_text(text, limit=_MAX_QUOTE_PREVIEW_CHARS),
        page_number=_positive_int(raw_item.get("page_number")),
        time_start_ms=_time_ms(raw_item, "start_ms"),
        time_end_ms=_time_ms(raw_item, "end_ms"),
        bbox=_bbox(raw_item.get("bbox")),
    )


def _safe_evidence_id(raw_item: Mapping[str, object], *, index: int) -> str:
    raw_id = safe_metadata_text(str(raw_item.get("id") or ""), limit=80).strip()
    return raw_id or f"element:{index}"


def _time_ms(raw_item: Mapping[str, object], key: str) -> int | None:
    time_range = raw_item.get("time_range")
    if not isinstance(time_range, Mapping):
        return None
    return _non_negative_int(time_range.get(key))


def _positive_int(value: object) -> int | None:
    parsed = _non_negative_int(value)
    return parsed if parsed is not None and parsed >= 1 else None


def _non_negative_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _bbox(value: object) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        parsed = tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if not all(isfinite(item) for item in parsed):
        return None
    return (parsed[0], parsed[1], parsed[2], parsed[3])


def _looks_like_prompt_injection(text: str) -> bool:
    return any(pattern.search(text) for pattern in _INJECTION_PATTERNS)


def _looks_sensitive(text: str) -> bool:
    if contains_sensitive_text(text):
        return True
    lowered = text.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)


def _init_diagnostics(diagnostics: dict[str, object]) -> None:
    diagnostics.setdefault("artifact_evidence_status", "unknown")
    for key in (
        "artifact_evidence_jobs_considered",
        "artifact_evidence_manifests_considered",
        "artifact_evidence_manifests_used",
        "artifact_evidence_items_considered",
        "artifact_evidence_items_used",
        "artifact_evidence_query_drop_count",
        "artifact_evidence_sensitive_drop_count",
        "artifact_evidence_prompt_injection_drop_count",
        "artifact_evidence_manifest_too_large_count",
        "artifact_evidence_read_error_count",
        "artifact_evidence_parse_error_count",
        "artifact_evidence_schema_skip_count",
        "artifact_evidence_stale_asset_drop_count",
    ):
        diagnostics.setdefault(key, 0)
