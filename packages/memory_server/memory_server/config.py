"""Memory server configuration."""

from enum import StrEnum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DeployProfile(StrEnum):
    TEST = "test"
    LOCAL = "local"
    CANARY = "canary"
    SERVER = "server"


class MemoryPolicyMode(StrEnum):
    DISABLED = "disabled"
    MANUAL_ONLY = "manual_only"
    SUGGESTIONS = "suggestions"
    ACTIVE_CONTEXT = "active_context"


class Settings(BaseSettings):
    service_name: str = "memory-platform"
    deploy_profile: DeployProfile = DeployProfile.LOCAL
    database_url: str = "postgresql+asyncpg://memory:memory@127.0.0.1:54329/memory"
    auto_create_schema: bool = False
    host: str = "127.0.0.1"
    port: int = 7788
    service_token: str | None = None
    policy_mode: MemoryPolicyMode = MemoryPolicyMode.ACTIVE_CONTEXT
    qdrant_enabled: bool = False
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "memory_chunks_v1"
    graphiti_enabled: bool = False
    graphiti_neo4j_uri: str = "bolt://127.0.0.1:7687"
    graphiti_neo4j_user: str = "neo4j"
    graphiti_neo4j_password: str | None = None
    graphiti_build_indices: bool = False
    cognee_enabled: bool = False
    cognee_runtime_configured: bool = False
    cognee_dataset_prefix: str = "memory"
    embeddings_enabled: bool = False
    embeddings_provider: str = "noop"
    embeddings_model: str = "text-embedding-3-small"
    embeddings_dimensions: int = Field(default=1536, ge=1, le=8192)
    openai_api_key: str | None = None
    legacy_hackinterview_enabled: bool = True
    default_space_slug: str = "default"
    default_profile_external_ref: str = "default"
    max_context_tokens: int = Field(default=1800, ge=256, le=16000)
    max_context_chars: int = Field(default=18000, ge=1000, le=60000)
    max_memory_candidates: int = Field(default=2000, ge=1, le=10000)
    max_memory_results: int = Field(default=32, ge=1, le=96)
    outbox_backpressure_pending_threshold: int = Field(default=0, ge=0)
    max_embedding_tokens_per_document: int = Field(default=0, ge=0)
    max_query_embeddings_per_minute: int = Field(default=0, ge=0)
    provider_circuit_failure_threshold: int = Field(default=3, ge=1, le=100)
    provider_circuit_reset_after_seconds: int = Field(default=60, ge=1, le=3600)

    model_config = SettingsConfigDict(
        env_prefix="MEMORY_",
        env_file=".env",
        extra="ignore",
    )

    def validate_for_startup(self) -> None:
        if self.deploy_profile == DeployProfile.SERVER and not self.service_token:
            raise RuntimeError("MEMORY_SERVICE_TOKEN is required for server profile")
        if self.deploy_profile == DeployProfile.SERVER and self.auto_create_schema:
            raise RuntimeError("MEMORY_AUTO_CREATE_SCHEMA is not allowed for server profile")
        if self.deploy_profile == DeployProfile.TEST and (
            self.qdrant_enabled or self.graphiti_enabled or self.embeddings_enabled
        ):
            raise RuntimeError("test profile cannot use external adapters")
        if self.qdrant_enabled and not self.embeddings_enabled:
            raise RuntimeError("MEMORY_QDRANT_ENABLED requires MEMORY_EMBEDDINGS_ENABLED")
        if self.embeddings_enabled and self.embeddings_provider != "openai":
            raise RuntimeError(
                "MEMORY_EMBEDDINGS_PROVIDER must be openai when embeddings are enabled"
            )
        if self.embeddings_enabled and not self.openai_api_key:
            raise RuntimeError("MEMORY_OPENAI_API_KEY is required when embeddings are enabled")
        if self.graphiti_enabled and not self.graphiti_neo4j_password:
            raise RuntimeError("MEMORY_GRAPHITI_ENABLED requires MEMORY_GRAPHITI_NEO4J_PASSWORD")
