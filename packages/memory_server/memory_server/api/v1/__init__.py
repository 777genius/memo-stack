"""Version 1 API routes."""

from fastapi import APIRouter

from memory_server.api.v1.capabilities import router as capabilities_router
from memory_server.api.v1.context import router as context_router
from memory_server.api.v1.diagnostics import router as diagnostics_router
from memory_server.api.v1.documents import router as documents_router
from memory_server.api.v1.episodes import router as episodes_router
from memory_server.api.v1.facts import router as facts_router
from memory_server.api.v1.health import router as health_router
from memory_server.api.v1.spaces_profiles import router as spaces_profiles_router
from memory_server.api.v1.suggestions import router as suggestions_router
from memory_server.api.v1.thread_memory import router as thread_memory_router

router = APIRouter(prefix="/v1")
router.include_router(health_router)
router.include_router(capabilities_router)
router.include_router(spaces_profiles_router)
router.include_router(facts_router)
router.include_router(documents_router)
router.include_router(episodes_router)
router.include_router(context_router)
router.include_router(thread_memory_router)
router.include_router(suggestions_router)
router.include_router(diagnostics_router)
