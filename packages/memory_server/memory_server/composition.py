"""Composition root for memory_server."""

from __future__ import annotations

from dataclasses import dataclass

from memory_adapters.noop import (
    NoopEmbeddingAdapter,
    NoopGraphMemoryAdapter,
    NoopVectorMemoryAdapter,
    SystemClock,
    UuidIdGenerator,
)
from memory_adapters.postgres import (
    PostgresUnitOfWorkFactory,
    build_async_engine,
    build_session_factory,
)
from memory_core.application import (
    ApproveSuggestionUseCase,
    BuildContextUseCase,
    CreateProfileUseCase,
    CreateSpaceUseCase,
    CreateSuggestionUseCase,
    DeleteDocumentUseCase,
    DeleteThreadMemoryUseCase,
    EnsureScopeUseCase,
    ExpireSuggestionUseCase,
    ForgetFactUseCase,
    GetCapabilitiesUseCase,
    GetDocumentUseCase,
    GetFactUseCase,
    GetSessionStatusUseCase,
    IngestDocumentUseCase,
    IngestEpisodeUseCase,
    ListDocumentChunksUseCase,
    ListFactsUseCase,
    ListFactVersionsUseCase,
    ListProfilesUseCase,
    ListSpacesUseCase,
    ListSuggestionsUseCase,
    ProcessDocumentUseCase,
    RejectSuggestionUseCase,
    RememberFactUseCase,
    UpdateFactUseCase,
)
from memory_core.application.context_packer import ContextPacker
from memory_core.ports.adapters import (
    EmbeddingPort,
    GraphMemoryPort,
    MemoryAdapterPort,
    VectorMemoryPort,
)
from memory_core.ports.clock import ClockPort
from memory_core.ports.ids import IdGeneratorPort
from memory_core.ports.unit_of_work import UnitOfWorkFactoryPort
from sqlalchemy.ext.asyncio import AsyncEngine

from memory_server.config import Settings

SUPPORTED_POLICY_MODES = (
    "disabled",
    "manual_only",
    "suggestions",
    "active_context",
)


@dataclass(frozen=True)
class Container:
    settings: Settings
    engine: AsyncEngine
    clock: ClockPort
    ids: IdGeneratorPort
    uow_factory: UnitOfWorkFactoryPort
    adapters: tuple[MemoryAdapterPort, ...]
    vector_index: VectorMemoryPort
    graph_index: GraphMemoryPort
    embedder: EmbeddingPort
    get_capabilities: GetCapabilitiesUseCase
    create_space: CreateSpaceUseCase
    list_spaces: ListSpacesUseCase
    create_profile: CreateProfileUseCase
    list_profiles: ListProfilesUseCase
    remember_fact: RememberFactUseCase
    list_facts: ListFactsUseCase
    get_fact: GetFactUseCase
    list_fact_versions: ListFactVersionsUseCase
    update_fact: UpdateFactUseCase
    forget_fact: ForgetFactUseCase
    ensure_scope: EnsureScopeUseCase
    ingest_episode: IngestEpisodeUseCase
    ingest_document: IngestDocumentUseCase
    get_document: GetDocumentUseCase
    list_document_chunks: ListDocumentChunksUseCase
    process_document: ProcessDocumentUseCase
    delete_document: DeleteDocumentUseCase
    build_context: BuildContextUseCase
    delete_thread_memory: DeleteThreadMemoryUseCase
    get_session_status: GetSessionStatusUseCase
    create_suggestion: CreateSuggestionUseCase
    list_suggestions: ListSuggestionsUseCase
    approve_suggestion: ApproveSuggestionUseCase
    reject_suggestion: RejectSuggestionUseCase
    expire_suggestion: ExpireSuggestionUseCase


def build_container(settings: Settings | None = None) -> Container:
    resolved_settings = settings or Settings()
    resolved_settings.validate_for_startup()

    clock = SystemClock()
    ids = UuidIdGenerator()
    engine = build_async_engine(resolved_settings.database_url)
    session_factory = build_session_factory(engine)
    uow_factory = PostgresUnitOfWorkFactory(session_factory=session_factory, clock=clock)

    vector = _build_vector_adapter(resolved_settings)
    graph = _build_graph_adapter(resolved_settings)
    embeddings = _build_embedding_adapter(resolved_settings)
    adapters: tuple[MemoryAdapterPort, ...] = (vector, graph, embeddings)

    get_capabilities = GetCapabilitiesUseCase(
        service_name=resolved_settings.service_name,
        deploy_profile=resolved_settings.deploy_profile.value,
        policy_mode=resolved_settings.policy_mode.value,
        adapters=adapters,
        supported_policy_modes=SUPPORTED_POLICY_MODES,
        limits={
            "max_context_tokens": resolved_settings.max_context_tokens,
            "max_context_chars": resolved_settings.max_context_chars,
            "max_memory_candidates": resolved_settings.max_memory_candidates,
            "max_memory_results": resolved_settings.max_memory_results,
        },
    )
    create_space = CreateSpaceUseCase(uow_factory=uow_factory, clock=clock, ids=ids)
    list_spaces = ListSpacesUseCase(uow_factory=uow_factory)
    create_profile = CreateProfileUseCase(uow_factory=uow_factory, clock=clock, ids=ids)
    list_profiles = ListProfilesUseCase(uow_factory=uow_factory)
    remember_fact = RememberFactUseCase(uow_factory=uow_factory, clock=clock, ids=ids)
    list_facts = ListFactsUseCase(uow_factory=uow_factory)
    get_fact = GetFactUseCase(uow_factory=uow_factory)
    list_fact_versions = ListFactVersionsUseCase(uow_factory=uow_factory)
    update_fact = UpdateFactUseCase(uow_factory=uow_factory, clock=clock)
    forget_fact = ForgetFactUseCase(uow_factory=uow_factory, clock=clock)
    ensure_scope = EnsureScopeUseCase(uow_factory=uow_factory, clock=clock)
    ingest_episode = IngestEpisodeUseCase(uow_factory=uow_factory, clock=clock, ids=ids)
    ingest_document = IngestDocumentUseCase(uow_factory=uow_factory, clock=clock, ids=ids)
    get_document = GetDocumentUseCase(uow_factory=uow_factory)
    list_document_chunks = ListDocumentChunksUseCase(uow_factory=uow_factory)
    process_document = ProcessDocumentUseCase(uow_factory=uow_factory)
    delete_document = DeleteDocumentUseCase(uow_factory=uow_factory, clock=clock)
    build_context = BuildContextUseCase(
        uow_factory=uow_factory,
        ids=ids,
        vector_index=vector,
        graph_index=graph,
        embedder=embeddings,
        packer=ContextPacker(),
    )
    delete_thread_memory = DeleteThreadMemoryUseCase(uow_factory=uow_factory)
    get_session_status = GetSessionStatusUseCase(uow_factory=uow_factory)
    create_suggestion = CreateSuggestionUseCase(uow_factory=uow_factory, clock=clock, ids=ids)
    list_suggestions = ListSuggestionsUseCase(uow_factory=uow_factory)
    approve_suggestion = ApproveSuggestionUseCase(uow_factory=uow_factory, clock=clock, ids=ids)
    reject_suggestion = RejectSuggestionUseCase(uow_factory=uow_factory, clock=clock)
    expire_suggestion = ExpireSuggestionUseCase(uow_factory=uow_factory, clock=clock)

    return Container(
        settings=resolved_settings,
        engine=engine,
        clock=clock,
        ids=ids,
        uow_factory=uow_factory,
        adapters=adapters,
        vector_index=vector,
        graph_index=graph,
        embedder=embeddings,
        get_capabilities=get_capabilities,
        create_space=create_space,
        list_spaces=list_spaces,
        create_profile=create_profile,
        list_profiles=list_profiles,
        remember_fact=remember_fact,
        list_facts=list_facts,
        get_fact=get_fact,
        list_fact_versions=list_fact_versions,
        update_fact=update_fact,
        forget_fact=forget_fact,
        ensure_scope=ensure_scope,
        ingest_episode=ingest_episode,
        ingest_document=ingest_document,
        get_document=get_document,
        list_document_chunks=list_document_chunks,
        process_document=process_document,
        delete_document=delete_document,
        build_context=build_context,
        delete_thread_memory=delete_thread_memory,
        get_session_status=get_session_status,
        create_suggestion=create_suggestion,
        list_suggestions=list_suggestions,
        approve_suggestion=approve_suggestion,
        reject_suggestion=reject_suggestion,
        expire_suggestion=expire_suggestion,
    )


def _build_vector_adapter(settings: Settings) -> MemoryAdapterPort:
    if not settings.qdrant_enabled:
        return NoopVectorMemoryAdapter(name="qdrant")
    from memory_adapters.qdrant import QdrantVectorMemoryAdapter

    return QdrantVectorMemoryAdapter(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        collection_name=settings.qdrant_collection,
        vector_size=settings.embeddings_dimensions,
    )


def _build_graph_adapter(settings: Settings) -> MemoryAdapterPort:
    if not settings.graphiti_enabled:
        return NoopGraphMemoryAdapter(name="graphiti")
    from memory_adapters.graphiti import GraphitiGraphMemoryAdapter

    return GraphitiGraphMemoryAdapter(
        neo4j_uri=settings.graphiti_neo4j_uri,
        neo4j_user=settings.graphiti_neo4j_user,
        neo4j_password=settings.graphiti_neo4j_password,
        build_indices=settings.graphiti_build_indices,
    )


def _build_embedding_adapter(settings: Settings) -> MemoryAdapterPort:
    if not settings.embeddings_enabled:
        return NoopEmbeddingAdapter(name="embeddings")
    if settings.embeddings_provider == "openai":
        from memory_adapters.embeddings import OpenAIEmbeddingAdapter

        return OpenAIEmbeddingAdapter(
            api_key=settings.openai_api_key,
            model=settings.embeddings_model,
            dimensions=settings.embeddings_dimensions,
        )
    return NoopEmbeddingAdapter(name="embeddings")
