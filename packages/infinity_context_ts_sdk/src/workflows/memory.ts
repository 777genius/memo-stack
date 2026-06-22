import type { ContextEnvelope, ContextBundleData, MemoryDigestData, SearchMemoryData } from "../context-types.js";
import { healthyRetrievalComponents, usedDerivedRetrieval } from "../diagnostics.js";
import { ValueError, type ReadScope, type ReadScopeInput, type SingleScopeInput } from "../payload.js";
import type { CapturesClient, CreateCaptureData, CreateCaptureInput } from "../resources/captures.js";
import type { ContextLinksClient, SuggestContextLinksData } from "../resources/context-links.js";
import type { BuildContextInput, BuildDigestInput, ContextClient } from "../resources/context.js";
import type { DocumentsClient } from "../resources/documents.js";
import type { FactsClient, RememberFactInput } from "../resources/facts.js";
import type { ApiEnvelope, DocumentRecord, FactRecord, JsonObject, SourceRef } from "../types.js";

export interface MemoryWorkflowResources {
  readonly captures: CapturesClient;
  readonly context: ContextClient;
  readonly contextLinks: ContextLinksClient;
  readonly documents: DocumentsClient;
  readonly facts: FactsClient;
}

export interface RecordMemoryFeedbackInput extends SingleScopeInput {
  readonly sourceAgent: string;
  readonly text: string;
  readonly idempotencyKey: string;
  readonly sourceId?: string;
  readonly sourceRefs?: readonly SourceRef[];
  readonly eventType?: string;
  readonly actorRole?: "user" | "assistant" | "tool" | "system" | "subagent" | "unknown";
  readonly sourceActorExternalRef?: string;
  readonly occurredAt?: string;
  readonly metadata?: JsonObject;
  readonly consolidate?: boolean;
  readonly rememberAsFact?: boolean;
  readonly factText?: string;
  readonly factKind?: string;
  readonly factCategory?: string;
  readonly factTags?: readonly string[];
  readonly factTtlPolicy?: string;
  readonly factMemoryScopeExternalRef?: string;
}

export interface RecordMemoryFeedbackResult {
  readonly capture: ApiEnvelope<CreateCaptureData>;
  readonly fact?: ApiEnvelope<FactRecord>;
}

export interface BuildMemoryBriefInput extends ReadScopeInput {
  readonly readScope?: ReadScope;
  readonly query: string;
  readonly topic?: string;
  readonly tokenBudget?: number;
  readonly maxFacts?: number;
  readonly maxChunks?: number;
  readonly maxEvidenceItems?: number;
  readonly includeSearch?: boolean;
  readonly includeDigest?: boolean;
  readonly digestTokenBudget?: number;
  readonly consistencyMode?: string;
  readonly includeStale?: boolean;
}

export interface MemoryBriefDiagnostics {
  readonly derivedRetrievalUsed: boolean;
  readonly vectorHealthy: boolean;
  readonly graphHealthy: boolean;
  readonly ragHealthy: boolean;
  readonly retrievalSourcesUsed: readonly string[];
  readonly warnings: readonly string[];
}

export interface BuildMemoryBriefResult {
  readonly context: ContextEnvelope<ContextBundleData>;
  readonly search?: ContextEnvelope<SearchMemoryData>;
  readonly digest?: ContextEnvelope<MemoryDigestData>;
  readonly diagnostics: MemoryBriefDiagnostics;
}

export type WorkflowStepOptions<TOptions extends object> = boolean | TOptions;

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

export interface RecordSourceEvidenceInput extends SingleScopeInput {
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

export interface MemoryWorkflowErrorData {
  readonly name: string;
  readonly message: string;
  readonly code?: string;
  readonly statusCode?: number;
  readonly retryable?: boolean;
  readonly requestId?: string;
}

export interface RecordSourceEvidenceBatchItemResult {
  readonly index: number;
  readonly sourceType: string;
  readonly sourceId: string;
  readonly idempotencyKey: string;
  readonly ok: boolean;
  readonly result?: RecordSourceEvidenceResult;
  readonly error?: MemoryWorkflowErrorData;
}

export interface RecordSourceEvidenceBatchInput {
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

export class MemoryWorkflows {
  constructor(private readonly resources: MemoryWorkflowResources) {}

  async recordFeedback(input: RecordMemoryFeedbackInput): Promise<RecordMemoryFeedbackResult> {
    const sourceRefs = feedbackSourceRefs(input);
    const captureInput: CreateCaptureInput = {
      ...singleScopeInput(input),
      sourceAgent: input.sourceAgent,
      sourceKind: "hook",
      eventType: input.eventType ?? "memory.feedback.recorded",
      actorRole: input.actorRole ?? "user",
      text: input.text,
      sourceEventId: input.sourceId ?? input.idempotencyKey,
      ...optional("sourceActorExternalRef", input.sourceActorExternalRef),
      evidenceRefs: sourceRefs,
      trustLevel: "high",
      sourceAuthority: input.actorRole === "assistant" ? "assistant_inference" : "user_statement",
      sensitivity: "medium",
      dataClassification: "internal",
      ...optional("occurredAt", input.occurredAt),
      ...optional("metadata", input.metadata),
      idempotencyKey: input.idempotencyKey,
      consolidate: input.consolidate ?? true,
    };

    const capture = await this.resources.captures.createCapture(captureInput);

    if (input.rememberAsFact === false) {
      return { capture };
    }

    const fact = await this.resources.facts.rememberFact({
      ...factScopeInput(input),
      text: input.factText ?? input.text,
      kind: input.factKind ?? "user_preference",
      category: input.factCategory ?? "feedback",
      tags: input.factTags ?? ["feedback"],
      ttlPolicy: input.factTtlPolicy ?? "durable",
      sourceRefs: [{ source_type: "capture", source_id: capture.data.id }, ...sourceRefs],
      idempotencyKey: `${input.idempotencyKey}:fact`,
    });

    return { capture, fact };
  }

  async recordSourceEvidence(input: RecordSourceEvidenceInput): Promise<RecordSourceEvidenceResult> {
    const baseSourceRefs = sourceEvidenceRefs(input);
    const createdSourceRefs: SourceRef[] = [];

    let document: ApiEnvelope<DocumentRecord> | undefined;
    let processedDocument: ApiEnvelope<DocumentRecord> | undefined;
    if (isEnabled(input.document, false)) {
      const documentOptions = stepOptions(input.document);
      document = await this.resources.documents.ingestDocument({
        ...singleScopeInput(input),
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
        processedDocument = await this.resources.documents.processDocument(document.data.id, {
          idempotencyKey: `${input.idempotencyKey}:document:process`,
        });
      }
    }

    let episode: ApiEnvelope<JsonObject> | undefined;
    if (isEnabled(input.episode, true)) {
      const episodeOptions = stepOptions(input.episode);
      episode = await this.resources.documents.ingestEpisode({
        ...singleScopeInput(input),
        sourceExternalId: input.sourceId,
        sourceType: input.sourceType,
        text: input.text,
        ...optional("occurredAt", episodeOptions.occurredAt ?? input.occurredAt),
        ...optional("speaker", episodeOptions.speaker),
        trustLevel: episodeOptions.trustLevel ?? "medium",
        kindHint: episodeOptions.kindHint ?? "source_evidence",
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
      capture = await this.resources.captures.createCapture({
        ...singleScopeInput(input),
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
      fact = await this.resources.facts.rememberFact({
        ...singleScopeInput(input),
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
      linkSuggestions = await this.resources.contextLinks.suggestContextLinks({
        ...singleScopeInput(input),
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

  async recordSourceEvidenceBatch(
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
          const result = await this.recordSourceEvidence(item);
          results[index] = batchItemResult(index, item, { result });
        } catch (error) {
          results[index] = batchItemResult(index, item, { error: workflowErrorData(error) });
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

  async buildMemoryBrief(input: BuildMemoryBriefInput): Promise<BuildMemoryBriefResult> {
    const contextInput: BuildContextInput = {
      ...readScopeInput(input),
      query: input.query,
      ...optional("tokenBudget", input.tokenBudget),
      ...optional("maxFacts", input.maxFacts),
      ...optional("maxChunks", input.maxChunks),
      ...optional("maxEvidenceItems", input.maxEvidenceItems),
      ...optional("consistencyMode", input.consistencyMode),
      ...optional("includeStale", input.includeStale),
    };

    const [context, search, digest] = await Promise.all([
      this.resources.context.buildContext(contextInput),
      input.includeSearch === false ? Promise.resolve(undefined) : this.resources.context.search(contextInput),
      input.includeDigest === false
        ? Promise.resolve(undefined)
        : this.resources.context.buildDigest({
            ...readScopeInput(input),
            topic: input.topic ?? input.query,
            ...optional("tokenBudget", input.digestTokenBudget ?? input.tokenBudget),
            ...optional("maxFacts", input.maxFacts),
            ...optional("maxChunks", input.maxChunks),
          } satisfies BuildDigestInput),
    ]);

    return {
      context,
      ...(search ? { search } : {}),
      ...(digest ? { digest } : {}),
      diagnostics: briefDiagnostics(context, search),
    };
  }
}

function sourceEvidenceRefs(input: RecordSourceEvidenceInput): readonly SourceRef[] {
  if (input.sourceRefs && input.sourceRefs.length > 0) {
    return input.sourceRefs;
  }
  return [{ source_type: input.sourceType, source_id: input.sourceId }];
}

function feedbackSourceRefs(input: RecordMemoryFeedbackInput): readonly SourceRef[] {
  if (input.sourceRefs && input.sourceRefs.length > 0) {
    return input.sourceRefs;
  }
  return [{ source_type: input.sourceAgent, source_id: input.sourceId ?? input.idempotencyKey }];
}

function singleScopeInput(input: SingleScopeInput): SingleScopeInput {
  return {
    ...optional("spaceId", input.spaceId),
    ...optional("memoryScopeId", input.memoryScopeId),
    ...optional("threadId", input.threadId),
    ...optional("spaceSlug", input.spaceSlug),
    ...optional("memoryScopeExternalRef", input.memoryScopeExternalRef),
    ...optional("threadExternalRef", input.threadExternalRef),
  };
}

function factScopeInput(input: RecordMemoryFeedbackInput): RememberFactInput {
  return {
    ...singleScopeInput(input),
    ...optional("memoryScopeExternalRef", input.factMemoryScopeExternalRef ?? input.memoryScopeExternalRef),
    text: input.factText ?? input.text,
    sourceRefs: feedbackSourceRefs(input),
  };
}

function readScopeInput(input: BuildMemoryBriefInput): ReadScopeInput & { readonly readScope?: ReadScope } {
  return {
    ...optional("readScope", input.readScope),
    ...optional("spaceId", input.spaceId),
    ...optional("memoryScopeIds", input.memoryScopeIds),
    ...optional("threadId", input.threadId),
    ...optional("spaceSlug", input.spaceSlug),
    ...optional("memoryScopeExternalRef", input.memoryScopeExternalRef),
    ...optional("memoryScopeExternalRefs", input.memoryScopeExternalRefs),
    ...optional("threadExternalRef", input.threadExternalRef),
  };
}

function briefDiagnostics(
  context: ContextEnvelope<ContextBundleData>,
  search?: ContextEnvelope<SearchMemoryData>,
): MemoryBriefDiagnostics {
  const contextDiagnostics = context.data.diagnostics;
  const searchDiagnostics = search?.data.diagnostics;
  return {
    derivedRetrievalUsed: usedDerivedRetrieval(contextDiagnostics)
      || (searchDiagnostics ? usedDerivedRetrieval(searchDiagnostics) : false),
    vectorHealthy: healthyRetrievalComponents(contextDiagnostics, ["vector"])
      || (searchDiagnostics ? healthyRetrievalComponents(searchDiagnostics, ["vector"]) : false),
    graphHealthy: healthyRetrievalComponents(contextDiagnostics, ["graph"])
      || (searchDiagnostics ? healthyRetrievalComponents(searchDiagnostics, ["graph"]) : false),
    ragHealthy: healthyRetrievalComponents(contextDiagnostics, ["rag"])
      || (searchDiagnostics ? healthyRetrievalComponents(searchDiagnostics, ["rag"]) : false),
    retrievalSourcesUsed: uniqueStrings([
      ...(contextDiagnostics.retrieval_sources_used ?? []),
      ...(searchDiagnostics?.retrieval_sources_used ?? []),
    ]),
    warnings: context.data.answer_support.warnings,
  };
}

function uniqueStrings(values: readonly string[]): readonly string[] {
  return [...new Set(values)];
}

function isEnabled<TOptions extends object>(
  value: WorkflowStepOptions<TOptions> | undefined,
  defaultValue: boolean,
): boolean {
  return value === undefined ? defaultValue : value !== false;
}

function stepOptions<TOptions extends object>(
  value: WorkflowStepOptions<TOptions> | undefined,
): Partial<TOptions> {
  return typeof value === "object" ? value : {};
}

function stringField(input: JsonObject, key: string): string | undefined {
  const value = input[key];
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function normalizeBatchConcurrency(value: number | undefined): number {
  if (value === undefined) {
    return 4;
  }
  if (!Number.isInteger(value) || value < 1 || value > 25) {
    throw new ValueError("recordSourceEvidenceBatch concurrency must be an integer from 1 to 25");
  }
  return value;
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

function workflowErrorData(error: unknown): MemoryWorkflowErrorData {
  const record = typeof error === "object" && error !== null ? error as Record<string, unknown> : {};
  const message = error instanceof Error ? error.message : String(error);
  const name = error instanceof Error ? error.name : "Error";
  const code = typeof record.code === "string" ? record.code : undefined;
  const statusCode = typeof record.statusCode === "number" ? record.statusCode : undefined;
  const retryable = typeof record.retryable === "boolean" ? record.retryable : undefined;
  const requestId = typeof record.requestId === "string" ? record.requestId : undefined;

  return {
    name,
    message,
    ...(code === undefined ? {} : { code }),
    ...(statusCode === undefined ? {} : { statusCode }),
    ...(retryable === undefined ? {} : { retryable }),
    ...(requestId === undefined ? {} : { requestId }),
  };
}

function isDefined<TValue>(value: TValue | undefined): value is TValue {
  return value !== undefined;
}

function ratio(value: number, total: number): number {
  return total <= 0 ? 0 : value / total;
}

function incrementCount(counts: Record<string, number>, key: string): void {
  counts[key] = (counts[key] ?? 0) + 1;
}

function optional<TKey extends string, TValue>(
  key: TKey,
  value: TValue | undefined,
): { readonly [K in TKey]?: TValue } {
  return value === undefined ? {} : { [key]: value } as { readonly [K in TKey]: TValue };
}
