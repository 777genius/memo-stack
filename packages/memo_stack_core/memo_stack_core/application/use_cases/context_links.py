"""Context-link use case facade.

Keep this module as the stable import path while implementation lives in smaller
Clean Architecture use case modules.
"""

from __future__ import annotations

from memo_stack_core.application.use_cases.context_link_crud import (
    CreateContextLinkUseCase,
    DeleteContextLinkUseCase,
    ListContextLinksUseCase,
    UpdateContextLinkUseCase,
)
from memo_stack_core.application.use_cases.context_link_reviews import (
    ListContextLinkSuggestionsUseCase,
    ReviewContextLinkSuggestionsBatchUseCase,
    ReviewContextLinkSuggestionUseCase,
)
from memo_stack_core.application.use_cases.context_link_suggestions import (
    SuggestContextLinksUseCase,
)

__all__ = [
    "CreateContextLinkUseCase",
    "DeleteContextLinkUseCase",
    "ListContextLinkSuggestionsUseCase",
    "ListContextLinksUseCase",
    "ReviewContextLinkSuggestionsBatchUseCase",
    "ReviewContextLinkSuggestionUseCase",
    "SuggestContextLinksUseCase",
    "UpdateContextLinkUseCase",
]
