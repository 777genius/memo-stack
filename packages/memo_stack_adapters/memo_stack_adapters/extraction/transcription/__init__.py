"""Speech transcription adapters used by extraction engines."""

from memo_stack_adapters.extraction.transcription.openai_adapter import (
    OpenAISpeechTranscriptionAdapter,
)

__all__ = ["OpenAISpeechTranscriptionAdapter"]
