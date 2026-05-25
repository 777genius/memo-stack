"""Capabilities API."""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from memory_server.api.auth import require_service_token
from memory_server.api.dependencies import get_container
from memory_server.composition import Container

router = APIRouter(tags=["capabilities"], dependencies=[Depends(require_service_token)])


@router.get("/capabilities")
async def capabilities(
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    result = await container.get_capabilities.execute()
    return {
        "api_version": "v1",
        "server_version": "0.1.0",
        "service_name": result.service_name,
        "deploy_profile": result.deploy_profile,
        "policy_mode": result.policy_mode,
        "adapters": {adapter.name: asdict(adapter) for adapter in result.adapters},
        "enabled_adapters": [
            adapter.name for adapter in result.adapters if adapter.enabled and adapter.healthy
        ],
        "supports_qdrant": any(adapter.name == "qdrant" for adapter in result.adapters),
        "supports_graphiti": any(adapter.name == "graphiti" for adapter in result.adapters),
        "supports_legacy_hackinterview_routes": container.settings.legacy_hackinterview_enabled,
        "supported_policy_modes": list(result.supported_policy_modes),
        "supported_embedding_models": [container.settings.embeddings_model],
        "limits": result.limits,
    }
