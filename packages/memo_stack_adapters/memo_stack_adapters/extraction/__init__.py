"""Extraction adapters for auto-memory candidate generation."""

from memo_stack_adapters.extraction.content import (
    ImageMetadataExtractionEngine,
    MediaMetadataExtractionEngine,
    PdfTextExtractionEngine,
    SimpleFileTypeDetector,
    SimpleTextExtractionEngine,
    StandardExtractionRouter,
    TimedTextTranscriptExtractionEngine,
    build_standard_extractor,
)
from memo_stack_adapters.extraction.docling_engine import DoclingDocumentExtractionEngine
from memo_stack_adapters.extraction.openai_json import OpenAIJsonMemoryExtractor
from memo_stack_adapters.extraction.openai_vision import OpenAIVisionImageExtractionEngine
from memo_stack_adapters.extraction.whisper_engine import FasterWhisperTranscriptionEngine

__all__ = [
    "DoclingDocumentExtractionEngine",
    "FasterWhisperTranscriptionEngine",
    "OpenAIJsonMemoryExtractor",
    "OpenAIVisionImageExtractionEngine",
    "ImageMetadataExtractionEngine",
    "MediaMetadataExtractionEngine",
    "PdfTextExtractionEngine",
    "SimpleFileTypeDetector",
    "SimpleTextExtractionEngine",
    "StandardExtractionRouter",
    "TimedTextTranscriptExtractionEngine",
    "build_standard_extractor",
]
