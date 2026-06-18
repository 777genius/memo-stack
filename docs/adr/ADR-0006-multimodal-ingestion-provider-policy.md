# ADR-0006 - Multimodal Ingestion Provider Policy

## Status

Accepted.

## Date

2026-06-13.

## Context

Memo Stack is moving from text-only memory into multimodal quick capture:
documents, screenshots, images, audio and video. The system must keep Clean
Architecture boundaries while still supporting strong extraction quality.

The risky simplification is to make one heavy local library the default for
everything:

```text
audio/video -> faster-whisper in the main server process
documents -> one parser library directly from use cases
images -> one vision/OCR path directly from use cases
```

That would create several problems:

- local ASR can saturate CPU/GPU, heat laptops and slow the desktop app;
- hosted/team deployments need independent scaling for long media jobs;
- self-hosted/private deployments still need a local/offline option;
- external provider calls need policy, audit, redaction and usage accounting;
- `memo_stack_core` must not import OpenAI, Docling, ffmpeg, Whisper or other
  provider/runtime packages.

## Decision

Use provider-neutral extraction and transcription ports. Keep all concrete
libraries and external APIs in adapters or future worker sidecars.

The default for audio/video transcription is **API-first**, with local ASR only
as an explicit opt-in profile.

```text
memo_stack_core
  ContentExtractionPort
  SpeechTranscriptionPort
  ImageUnderstandingPort
  neutral DTOs only

memo_stack_adapters
  docling document adapter
  local text/pdf/image/media metadata adapters
  OpenAI transcription adapter
  future Deepgram/AssemblyAI transcription adapters
  faster-whisper local transcription adapter
  OpenAI vision adapter
  ffmpeg/ffprobe media adapter

memo_stack_server
  config, policy, provider registry, composition root, diagnostics
```

### Audio

Default route:

```text
asset audio file
  -> MIME/signature detection
  -> ffprobe duration/stream metadata
  -> SpeechTranscriptionPort
  -> default provider: external API when policy allows
  -> transcript artifact + timecoded ExtractedElement items
  -> canonical MemoryDocument/MemoryChunk with source refs
```

Default API provider for the first implementation:

```text
openai:gpt-4o-mini-transcribe
```

Local provider:

```text
faster-whisper
```

Local ASR is never the silent default. It is enabled only by an explicit profile
or deployment config, for example:

```text
MEMORY_TRANSCRIPTION_PROVIDER=local_faster_whisper
MEMORY_EXTRACTION_PROFILE=media_local_asr
```

Public capability diagnostics must expose this as a contract, not only as
implementation behavior:

```text
policy.local_asr_default = false
policy.local_asr_requires_explicit_profile = true
profile.media_api.may_run_local_asr = false
profile.standard_full.may_run_local_asr = false
profile.media_local_asr.may_run_local_asr = true
profile.standard_asr.deprecated = true
profile.standard_asr.replacement_profiles = [media_api, media_local_asr]
```

`standard_asr` remains a compatibility/deprecation profile for API-first
transcription. It must not silently fall back to local ASR when the API provider
is disabled, missing credentials, over upload limits or unavailable. The safe
fallback is metadata/keyframe evidence through the local media extractor.

### Video

Video is not a document parser problem. Video extraction is a media pipeline:

```text
asset video file
  -> ffprobe streams/duration/codecs/resolution
  -> extract or stream audio track when present
  -> SpeechTranscriptionPort for transcript
  -> optional scene/keyframe extraction
  -> optional OCR/vision on selected frames
  -> transcript/keyframe artifacts + timecoded chunks
```

The first reliable implementation should support:

- metadata-only fallback when no transcription provider is available;
- audio transcript when the video has an audio stream;
- selected keyframes only when within limits;
- source refs with `time_start_ms`, `time_end_ms`, optional `bbox` and provider
  diagnostics.

### Documents

Documents use a document parser profile, not the transcription provider.

Recommended route:

```text
PDF/DOCX/PPTX/XLSX/HTML/text/image-like document
  -> MIME/signature detection
  -> Docling adapter when installed and profile allows it
  -> local fallback adapters such as pypdf/plain/html/csv/image metadata
  -> future sidecar/cloud parser only when policy allows it
  -> canonical document/chunk ingest
```

Docling is the primary optional document parser because it gives structured
document output, but parser-specific objects never cross into `memo_stack_core`.

### Images And Screenshots

Images are evidence first, not facts.

Recommended route:

```text
image/screenshot
  -> local metadata and dimensions
  -> OCR when local profile supports it
  -> optional vision adapter when external AI policy allows it
  -> extracted elements with confidence and bbox when known
  -> capture/link suggestions, not direct fact mutation
```

## Provider Governance

External provider calls require all of these:

- space or memory-scope policy allows external processing;
- provider API key/config is present;
- budget/quota admission succeeds before enqueueing expensive work;
- sensitive metadata is redacted or dropped before egress when policy requires;
- timeout, retry and safe error classification are configured;
- resulting text is stored as evidence with source refs, not trusted
  instructions.

Usage accounting must track at least:

```text
media_analysis_seconds_requested
media_analysis_seconds_actual
provider_name
provider_model
estimated_cost_units
reconciled_usage_delta
```

## Dependency Policy

Required baseline dependencies should stay small.

Recommended optional extras:

```text
docling
  docling>=2.102.1,<3.0.0

transcription-openai
  openai>=2.41.1,<3.0.0

transcription-local
  faster-whisper>=1.2.1,<2.0.0

video
  scenedetect>=0.7,<1.0.0

filetype
  filetype>=1.2.0,<2.0.0
```

`ffmpeg` and `ffprobe` are system dependencies. They must be reported through
diagnostics/capabilities instead of being assumed available.

Do not add Celery, LangChain, LlamaIndex, EasyOCR, Marker, MinerU, NVIDIA
ingest, cloud Document AI SDKs or Tika as default runtime dependencies. They
can be future adapters or sidecars after quality, license and operational
review.

## Consequences

Positive:

- desktop usage stays responsive by default;
- hosted/team deployments can use managed ASR without GPU workers;
- self-hosted/private deployments can opt into local ASR;
- provider changes do not rewrite core use cases;
- usage/cost governance is explicit;
- audio/video extraction can scale into a separate worker service later.

Tradeoffs:

- external ASR requires API keys and egress policy;
- local/offline users must explicitly install and configure the heavier ASR
  extra;
- tests must cover provider routing, not only parser output;
- capabilities/diagnostics become product-critical.

## Implementation Order

1. Add or refine neutral provider ports and DTOs for transcription/image
   understanding without importing provider packages in core.
2. Add provider registry and routing policy in the server composition root.
3. Make audio/video metadata extraction reliable through ffprobe/ffmpeg.
4. Implement API transcription adapter first.
5. Keep faster-whisper as optional local adapter.
6. Persist transcript artifacts and timecoded source refs.
7. Add video keyframe/scene extraction behind limits.
8. Add frontend status/cost/provenance display for media jobs.

This ADR supersedes any plan language that implies faster-whisper is the default
ASR path.
