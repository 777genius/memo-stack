"""Embedding adapters package."""

from infinity_context_adapters.embeddings.noop_adapter import NoopEmbeddingAdapter
from infinity_context_adapters.embeddings.openai_adapter import OpenAIEmbeddingAdapter

__all__ = ["NoopEmbeddingAdapter", "OpenAIEmbeddingAdapter"]
