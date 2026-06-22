import type { RequestControls } from "../client.js";
import { ValueError, type SingleScopeInput } from "../payload.js";
import type { CapturesClient, CreateCaptureData, CreateCaptureInput } from "../resources/captures.js";
import type { ContextLinksClient, SuggestContextLinksData } from "../resources/context-links.js";
import type { DocumentsClient } from "../resources/documents.js";
import type { FactsClient } from "../resources/facts.js";
import type { ApiEnvelope, DocumentRecord, FactRecord, JsonObject, SourceRef } from "../types.js";
import {
  incrementCount,
  isDefined,
  isEnabled,
  normalizeBatchConcurrency,
  optional,
  ratio,
  singleScopeInput,
  stepOptions,
  stringField,
  withWorkflowControls,
  workflowControls,
  workflowErrorData,
  type WorkflowErrorData,
  type WorkflowStepOptions,
} from "./workflow-helpers.js";

export interface SourceEvidenceResources {
  readonly captures: CapturesClient;
  readonly contextLinks: ContextLinksClient;
  readonly documents: DocumentsClient;
  readonly facts: FactsClient;
}

export interface RecordSourceEvidenceDocumentOptions {
  readonly title?: string;
  readonly classification?: string;
  readonly process?: boolean;
}

export interface RecordSourceEvidenceEpisodeOptions {
  readonly occurredAt?: string;
  readonly speaker?: string;
  readonly trustLevel?: string;
  readonly kindHint?: string;
  readonly language?: string;
  readonly metadata?: JsonObject;
}

export interface RecordSourceEvidenceCaptureOptions {
  readonly sourceKind?: CreateCaptureInput["sourceKind"];
  readonly eventType?: string;
  readonly actorRole?: CreateCaptureInput["actorRole"];
  readonly sourceActorExternalRef?: string;
  readonly clientInstanceId?: string;
  readonly traceId?: string;
  readonly trustLevel?: CreateCaptureInput["trustLevel"];
  readonly sourceAuthority?: CreateCaptureInput["sourceAuthority"];
  readonly sensitivity?: CreateCaptureInput["sensitivity"];
  readonly dataClassification?: CreateCaptureInput["dataClassification"];
  readonly consolidate?: boolean;
}

export interface RecordSourceEvidenceFactOptions {
  readonly text?: string;
  readonly memoryScopeExternalRef?: string;
  readonly kind?: string;
  readonly category?: string;
  readonly tags?: readonly string[];
  readonly ttlPolicy?: string;
}

export interface RecordSourceEvidenceLinkSuggestionOptions {
  readonly persist?: boolean;
  readonly limit?: number;
  readonly sourceType?: string;
  readonly sourceId?: string;
}

export interface RecordSourceEvidenceInput extends SingleScopeInput, RequestControls {
  readonly sourceAgent: string;
  readonly sourceType: string;
  readonly sourceId: string;
  readonly text: string;
  readonly idempotencyKey: string;
  readonly title?: string;
  readonly occurredAt?: string;
  readonly sourceRefs?: readonly SourceRef[];
  readonly metadata?: JsonObject;
  readonly document?: WorkflowStepOptions<RecordSourceEvidenceDocumentOptions>;
  readonly episode?: WorkflowStepOptions<RecordSourceEvidenceEpisodeOptions>;
  readonly capture?: WorkflowStepOptions<RecordSourceEvidenceCaptureOptions>;
  readonly fact?: WorkflowStepOptions<RecordSourceEvidenceFactOptions>;
  readonly linkSuggestions?: WorkflowStepOptions<RecordSourceEvidenceLinkSuggestionOptions>;
}

export interface RecordSourceEvidenceResult {
  readonly sourceRefs: readonly SourceRef[];
  readonly document?: ApiEnvelope<DocumentRecord>;
  readonly processedDocument?: ApiEnvelope<DocumentRecord>;
  readonly episode?: ApiEnvelope<JsonObject>;
  readonly capture?: ApiEnvelope<CreateCaptureData>;
  readonly fact?: ApiEnvelope<FactRecord>;
  readonly linkSuggestions?: ApiEnvelope<SuggestContextLinksData>;
}

export type MemoryWorkflowErrorData = WorkflowErrorData;

export interface RecordSourceEvidenceBatchItemResult {
  readonly index: number;
  readonly sourceType: string;
  readonly sourceId: string;
  readonly idempotencyKey: string;
  readonly ok: boolean;
  readonly result?: RecordSourceEvidenceResult;
  readonly error?: MemoryWorkflowErrorData;
}

export interface RecordSourceEvidenceBatchInput extends RequestControls {
  readonly items: readonly RecordSourceEvidenceInput[];
  readonly concurrency?: number;
  readonly continueOnError?: boolean;
}

export interface RecordSourceEvidenceBatchResult {
  readonly total: number;
  readonly succeeded: number;
  readonly failed: number;
  readonly stopped: boolean;
  readonly results: readonly RecordSourceEvidenceBatchItemResult[];
}

export interface RecordSourceEvidenceBatchFailure {
  readonly index: number;
  readonly sourceType: string;
  readonly sourceId: string;
  readonly idempotencyKey: string;
  readonly error: MemoryWorkflowErrorData;
}

export interface RecordSourceEvidenceBatchSummary {
  readonly total: number;
  readonly completed: number;
  readonly skipped: number;
  readonly succeeded: number;
  readonly failed: number;
  readonly stopped: boolean;
  readonly successRate: number;
  readonly failureRate: number;
  readonly retryableFailures: number;
  readonly nonRetryableFailures: number;
  readonly bySourceType: Readonly<Record<string, number>>;
  readonly byErrorCode: Readonly<Record<string, number>>;
  readonly byStatusCode: Readonly<Record<string, number>>;
  readonly failedItems: readonly RecordSourceEvidenceBatchFailure[];
}

export function summarizeSourceEvidenceBatch(
  batch: RecordSourceEvidenceBatchResult,
): RecordSourceEvidenceBatchSummary {
  const bySourceType: Record<string, number> = {};
  const byErrorCode: Record<string, number> = {};
  const byStatusCode: Record<string, number> = {};
  const failedItems: RecordSourceEvidenceBatchFailure[] = [];
  let retryableFailures = 0;
  let nonRetryableFailures = 0;

  for (const item of batch.results) {
    incrementCount(bySourceType, item.sourceType);

    if (item.ok || item.error === undefined) {
      continue;
    }

    const errorCode = item.error.code ?? "unknown";
    const statusCode = item.error.statusCode === undefined ? "unknown" : String(item.error.statusCode);
    incrementCount(byErrorCode, errorCode);
    incrementCount(byStatusCode, statusCode);

    if (item.error.retryable === true) {
      retryableFailures += 1;
    } else {
      nonRetryableFailures += 1;
    }

    failedItems.push({
      index: item.index,
      sourceType: item.sourceType,
      sourceId: item.sourceId,
      idempotencyKey: item.idempotencyKey,
      error: item.error,
    });
  }

  const completed = batch.results.length;
  const skipped = Math.max(0, batch.total - completed);
  return {
    total: batch.total,
    completed,
    skipped,
    succeeded: batch.succeeded,
    failed: batch.failed,
    stopped: batch.stopped,
    successRate: ratio(batch.succeeded, batch.total),
    failureRate: ratio(batch.failed, batch.total),
    retryableFailures,
    nonRetryableFailures,
    bySourceType,
    byErrorCode,
    byStatusCode,
    failedItems,
  };
}

export async function recordSourceEvidence(
  resources: SourceEvidenceResources,
  input: RecordSourceEvidenceInput,
): Promise<RecordSourceEvidenceResult> {
  const baseSourceRefs = sourceEvidenceRefs(input);
  const createdSourceRefs: SourceRef[] = [];
  const controls = workflowControls(input);

  let document: ApiEnvelope<DocumentRecord> | undefined;
  let processedDocument: ApiEnvelope<DocumentRecord> | undefined;
  if (isEnabled(input.document, false)) {
    const documentOptions = stepOptions(input.document);
    document = await resources.documents.ingestDocument({
      ...singleScopeInput(input),
      ...controls,
      title: documentOptions.title ?? input.title ?? input.sourceId,
      text: input.text,
      sourceExternalId: input.sourceId,
      sourceType: input.sourceType,
      classification: documentOptions.classification ?? "internal",
      sourceRefs: baseSourceRefs,
      idempotencyKey: `${input.idempotencyKey}:document`,
    });
    createdSourceRefs.push({ source_type: "document", source_id: document.data.id });

    if (documentOptions.process === true) {
      processedDocument = await resources.documents.processDocument(document.data.id, {
        ...controls,
        idempotencyKey: `${input.idempotencyKey}:document:process`,
      });
    }
  }

  let episode: ApiEnvelope<JsonObject> | undefined;
  if (isEnabled(input.episode, true)) {
    const episodeOptions = stepOptions(input.episode);
    episode = await resources.documents.ingestEpisode({
      ...singleScopeInput(input),
      ...controls,
      sourceExternalId: input.sourceId,
      sourceType: input.sourceType,
      text: input.text,
      ...optional("occurredAt", episodeOptions.occurredAt ?? input.occurredAt),
      ...optional("speaker", episodeOptions.speaker),
      trustLevel: episodeOptions.trustLevel ?? "medium",
      kindHint: episodeOptions.kindHint ?? "fact_evidence",
      ...optional("language", episodeOptions.language),
      metadata: { ...input.metadata, ...episodeOptions.metadata },
      idempotencyKey: `${input.idempotencyKey}:episode`,
    });
    const episodeId = stringField(episode.data, "id");
    if (episodeId) {
      createdSourceRefs.push({ source_type: "episode", source_id: episodeId });
    }
  }

  let capture: ApiEnvelope<CreateCaptureData> | undefined;
  if (isEnabled(input.capture, true)) {
    const captureOptions = stepOptions(input.capture);
    capture = await resources.captures.createCapture({
      ...singleScopeInput(input),
      ...controls,
      sourceAgent: input.sourceAgent,
      sourceKind: captureOptions.sourceKind ?? "document",
      eventType: captureOptions.eventType ?? "memory.source_evidence.recorded",
      actorRole: captureOptions.actorRole ?? "tool",
      text: input.text,
      sourceEventId: input.sourceId,
      ...optional("sourceActorExternalRef", captureOptions.sourceActorExternalRef),
      ...optional("clientInstanceId", captureOptions.clientInstanceId),
      evidenceRefs: [...baseSourceRefs, ...createdSourceRefs],
      trustLevel: captureOptions.trustLevel ?? "medium",
      sourceAuthority: captureOptions.sourceAuthority ?? "tool_verified",
      sensitivity: captureOptions.sensitivity ?? "medium",
      dataClassification: captureOptions.dataClassification ?? "internal",
      ...optional("occurredAt", input.occurredAt),
      ...optional("metadata", input.metadata),
      ...optional("traceId", captureOptions.traceId),
      idempotencyKey: `${input.idempotencyKey}:capture`,
      consolidate: captureOptions.consolidate ?? true,
    });
    createdSourceRefs.push({ source_type: "capture", source_id: capture.data.id });
  }

  let fact: ApiEnvelope<FactRecord> | undefined;
  if (isEnabled(input.fact, false)) {
    const factOptions = stepOptions(input.fact);
    fact = await resources.facts.rememberFact({
      ...singleScopeInput(input),
      ...controls,
      ...optional("memoryScopeExternalRef", factOptions.memoryScopeExternalRef ?? input.memoryScopeExternalRef),
      text: factOptions.text ?? input.text,
      kind: factOptions.kind ?? "source_signal",
      category: factOptions.category ?? "source_evidence",
      tags: factOptions.tags ?? [input.sourceType],
      ttlPolicy: factOptions.ttlPolicy ?? "durable",
      sourceRefs: [...createdSourceRefs, ...baseSourceRefs],
      idempotencyKey: `${input.idempotencyKey}:fact`,
    });
  }

  let linkSuggestions: ApiEnvelope<SuggestContextLinksData> | undefined;
  if (isEnabled(input.linkSuggestions, true)) {
    const linkOptions = stepOptions(input.linkSuggestions);
    linkSuggestions = await resources.contextLinks.suggestContextLinks({
      ...singleScopeInput(input),
      ...controls,
      text: input.text,
      sourceType: linkOptions.sourceType ?? (capture ? "capture" : input.sourceType),
      sourceId: linkOptions.sourceId ?? capture?.data.id ?? input.sourceId,
      limit: linkOptions.limit ?? 10,
      persist: linkOptions.persist ?? true,
    });
  }

  return {
    sourceRefs: [...baseSourceRefs, ...createdSourceRefs],
    ...(document ? { document } : {}),
    ...(processedDocument ? { processedDocument } : {}),
    ...(episode ? { episode } : {}),
    ...(capture ? { capture } : {}),
    ...(fact ? { fact } : {}),
    ...(linkSuggestions ? { linkSuggestions } : {}),
  };
}

export async function recordSourceEvidenceBatch(
  resources: SourceEvidenceResources,
  input: RecordSourceEvidenceBatchInput,
): Promise<RecordSourceEvidenceBatchResult> {
  const concurrency = normalizeBatchConcurrency(input.concurrency);
  const items = [...input.items];
  if (items.length > 500) {
    throw new ValueError("recordSourceEvidenceBatch supports at most 500 items");
  }
  if (items.length === 0) {
    return { total: 0, succeeded: 0, failed: 0, stopped: false, results: [] };
  }

  const continueOnError = input.continueOnError ?? true;
  const results: Array<RecordSourceEvidenceBatchItemResult | undefined> = [];
  let nextIndex = 0;
  let stopped = false;

  const workerCount = Math.min(concurrency, items.length);
  await Promise.all(Array.from({ length: workerCount }, async () => {
    for (;;) {
      if (stopped) {
        return;
      }

      const index = nextIndex;
      nextIndex += 1;
      const item = items[index];
      if (item === undefined) {
        return;
      }

      try {
        const scopedItem = withWorkflowControls(input, item);
        const result = await recordSourceEvidence(resources, scopedItem);
        results[index] = batchItemResult(index, scopedItem, { result });
      } catch (error) {
        const scopedItem = withWorkflowControls(input, item);
        results[index] = batchItemResult(index, scopedItem, { error: workflowErrorData(error) });
        if (!continueOnError) {
          stopped = true;
          return;
        }
      }
    }
  }));

  const completedResults = results.filter(isDefined);
  const failed = completedResults.filter((result) => !result.ok).length;
  return {
    total: items.length,
    succeeded: completedResults.length - failed,
    failed,
    stopped,
    results: completedResults,
  };
}

function sourceEvidenceRefs(input: RecordSourceEvidenceInput): readonly SourceRef[] {
  if (input.sourceRefs && input.sourceRefs.length > 0) {
    return input.sourceRefs;
  }
  return [{ source_type: input.sourceType, source_id: input.sourceId }];
}

function batchItemResult(
  index: number,
  input: RecordSourceEvidenceInput,
  outcome: { readonly result: RecordSourceEvidenceResult } | { readonly error: MemoryWorkflowErrorData },
): RecordSourceEvidenceBatchItemResult {
  return {
    index,
    sourceType: input.sourceType,
    sourceId: input.sourceId,
    idempotencyKey: input.idempotencyKey,
    ok: "result" in outcome,
    ...("result" in outcome ? { result: outcome.result } : { error: outcome.error }),
  };
}
