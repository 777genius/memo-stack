"""Embedding adapters package."""

from memory_adapters.embeddings.noop_adapter import NoopEmbeddingAdapter
from memory_adapters.embeddings.openai_adapter import OpenAIEmbeddingAdapter

__all__ = ["NoopEmbeddingAdapter", "OpenAIEmbeddingAdapter"]
