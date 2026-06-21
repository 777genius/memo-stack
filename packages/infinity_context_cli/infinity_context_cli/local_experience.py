"""Shared local first-use experience payload helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

VISUAL_MEMORY_TABS = (
    "Capture",
    "Overview",
    "Graph",
    "Review",
    "Operations",
    "Timeline",
)

BASE_CAPTURE_SUPPORT = ("text_note", "file_evidence")

_MODALITY_SUPPORT = {
    "document": "document_file",
    "image": "image_or_screenshot",
    "timed_text": "timed_text_file",
    "audio": "audio_transcription",
    "video": "video_keyframes_transcript",
    "audio_metadata": "audio_metadata_file",
    "video_metadata": "video_metadata_file",
}


def build_first_capture_surface(
    *,
    capabilities: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a bounded, user-facing description of the first capture surface."""
    capability_data = _capability_data(capabilities)
    active_modalities = _active_modalities(capability_data)
    support = _capture_support(active_modalities)
    suggestions = _mapping(capability_data.get("suggestions"))
    context = _mapping(capability_data.get("context"))
    review_supported = suggestions.get("review_tool_supported") is True
    artifact_previews = _artifact_previews(active_modalities)

    return {
        "surface": "visual_memory_browser",
        "tab": "Capture",
        "supports": list(support),
        "active_modalities": active_modalities,
        "artifact_previews": artifact_previews,
        "review_supported": review_supported,
        "review_actions": ["approve", "reject", "edit_target"] if review_supported else [],
        "answer_support_supported": context.get("answer_support_supported") is True,
        "visual_memory_tabs": list(VISUAL_MEMORY_TABS),
    }


def build_one_minute_path(
    *,
    api_url: str,
    agents: Sequence[str],
    runtime_ready: bool,
    visual_ready: bool,
    mcp_ready: bool,
    first_capture: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return a concise first-run checklist for humans and installers."""
    agent = next((item for item in agents if item), "codex")
    return [
        {
            "id": "start_runtime",
            "status": "done" if runtime_ready else "todo",
            "command": "infinity-context up --lite",
        },
        {
            "id": "open_visual_memory",
            "status": "done" if visual_ready else "todo",
            "command": "infinity-context ui --open",
            "url": _ui_url(api_url),
        },
        {
            "id": "connect_agent_mcp",
            "status": "done" if mcp_ready else "todo",
            "command": f"infinity-context mcp-config --agent {agent} --write",
            "agents": list(agents),
        },
        {
            "id": "save_first_memory",
            "status": "next" if visual_ready else "blocked",
            "surface": first_capture.get("surface"),
            "tab": first_capture.get("tab"),
            "supports": list(_sequence(first_capture.get("supports"))),
        },
        {
            "id": "review_or_link",
            "status": "ready" if first_capture.get("review_supported") else "degraded",
            "tab": "Review",
            "actions": list(_sequence(first_capture.get("review_actions"))),
        },
    ]


def local_experience_score(
    *,
    runtime_ready: bool,
    visual_ready: bool,
    mcp_ready: bool,
    first_capture: Mapping[str, Any],
) -> dict[str, Any]:
    """Score only first-use readiness, not memory intelligence quality."""
    checks = {
        "runtime_ready": runtime_ready,
        "visual_memory_ready": visual_ready,
        "mcp_ready": mcp_ready,
        "capture_surface_documented": bool(first_capture.get("supports")),
        "review_supported": first_capture.get("review_supported") is True,
    }
    passed = sum(1 for ok in checks.values() if ok)
    total = len(checks)
    return {
        "score": round((passed / total) * 10, 1),
        "scale": 10,
        "checks": checks,
        "note": "first_use_readiness_only",
    }


def _capability_data(capabilities: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(capabilities, Mapping):
        return {}
    data = capabilities.get("data")
    if isinstance(data, Mapping):
        return data
    return capabilities


def _active_modalities(capabilities: Mapping[str, Any]) -> list[str]:
    extraction = _mapping(capabilities.get("extraction"))
    profiles = extraction.get("profiles_v2")
    if not isinstance(profiles, list):
        return []

    modalities: set[str] = set()
    for profile in profiles:
        if not isinstance(profile, Mapping):
            continue
        if profile.get("enabled") is False:
            continue
        if str(profile.get("status") or "").lower() not in {"ok", "degraded"}:
            continue
        for modality in _sequence(profile.get("input_modalities")):
            modality = str(modality).strip()
            if modality:
                modalities.add(modality)
    return sorted(modalities)


def _capture_support(active_modalities: Sequence[str]) -> tuple[str, ...]:
    support = list(BASE_CAPTURE_SUPPORT)
    for modality in active_modalities:
        label = _MODALITY_SUPPORT.get(modality)
        if label and label not in support:
            support.append(label)
    return tuple(support)


def _artifact_previews(active_modalities: Sequence[str]) -> list[str]:
    previews = {"capture_preview", "source_quote"}
    if any(item in active_modalities for item in ("document", "timed_text")):
        previews.add("document_chunks")
    if "image" in active_modalities:
        previews.add("image_regions")
    if any(item in active_modalities for item in ("audio", "video")):
        previews.add("transcript_segments")
    if "video" in active_modalities:
        previews.add("keyframes")
    return sorted(previews)


def _ui_url(api_url: str) -> str:
    return f"{api_url.rstrip('/')}/ui/"


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[object]:
    if isinstance(value, list | tuple):
        return value
    return ()
