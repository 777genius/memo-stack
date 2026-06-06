"""HTTP-layer policy guards for Core Lite modes."""

from __future__ import annotations

from memory_core.domain.errors import MemoryPolicyBlockedError

from memory_server.composition import Container
from memory_server.config import MemoryPolicyMode


def ensure_server_writes_enabled(container: Container) -> None:
    if container.settings.policy_mode == MemoryPolicyMode.DISABLED:
        raise MemoryPolicyBlockedError("Memory writes are disabled by policy")


def should_retrieve(container: Container) -> bool:
    return container.settings.policy_mode in {
        MemoryPolicyMode.MANUAL_ONLY,
        MemoryPolicyMode.SUGGESTIONS,
        MemoryPolicyMode.ACTIVE_CONTEXT,
    }


def should_ingest_legacy_transcript(container: Container) -> bool:
    return container.settings.policy_mode in {
        MemoryPolicyMode.SUGGESTIONS,
        MemoryPolicyMode.ACTIVE_CONTEXT,
    }


def should_capture(container: Container) -> bool:
    return container.settings.policy_mode in {
        MemoryPolicyMode.SUGGESTIONS,
        MemoryPolicyMode.ACTIVE_CONTEXT,
    }
