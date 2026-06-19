"""Speech transcription adapters used by extraction engines."""

from infinity_context_adapters.extraction.transcription.openai_adapter import (
    OpenAISpeechTranscriptionAdapter,
    openai_transcription_request_contract,
)

__all__ = [
    "OpenAISpeechTranscriptionAdapter",
    "openai_transcription_request_contract",
]
