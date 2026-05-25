"""Capability discovery use case."""

from __future__ import annotations

from dataclasses import dataclass

from memory_core.ports.adapters import AdapterCapabilities, MemoryAdapterPort


@dataclass(frozen=True)
class CapabilitiesResult:
    service_name: str
    deploy_profile: str
    policy_mode: str
    adapters: tuple[AdapterCapabilities, ...]
    supported_policy_modes: tuple[str, ...]
    limits: dict[str, int]


class GetCapabilitiesUseCase:
    def __init__(
        self,
        *,
        service_name: str,
        deploy_profile: str,
        policy_mode: str,
        adapters: tuple[MemoryAdapterPort, ...],
        supported_policy_modes: tuple[str, ...],
        limits: dict[str, int],
    ) -> None:
        self._service_name = service_name
        self._deploy_profile = deploy_profile
        self._policy_mode = policy_mode
        self._adapters = adapters
        self._supported_policy_modes = supported_policy_modes
        self._limits = limits

    async def execute(self) -> CapabilitiesResult:
        capabilities = []
        for adapter in self._adapters:
            capabilities.append(await adapter.capabilities())
        return CapabilitiesResult(
            service_name=self._service_name,
            deploy_profile=self._deploy_profile,
            policy_mode=self._policy_mode,
            adapters=tuple(capabilities),
            supported_policy_modes=self._supported_policy_modes,
            limits=dict(self._limits),
        )
