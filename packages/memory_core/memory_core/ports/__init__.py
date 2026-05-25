"""Ports exposed by memory_core."""

from memory_core.ports.adapters import (
    AdapterCapabilities,
    GraphCandidate,
    GraphSearchResult,
    MemoryAdapterPort,
    PortDiagnostic,
    PortStatus,
    VectorCandidate,
    VectorSearchResult,
)
from memory_core.ports.clock import ClockPort
from memory_core.ports.ids import IdGeneratorPort

__all__ = [
    "AdapterCapabilities",
    "ClockPort",
    "GraphCandidate",
    "GraphSearchResult",
    "IdGeneratorPort",
    "MemoryAdapterPort",
    "PortDiagnostic",
    "PortStatus",
    "VectorCandidate",
    "VectorSearchResult",
]
