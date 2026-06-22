import type { ContextEnvelope, ContextBundleData, MemoryDigestData, SearchMemoryData } from "../context-types.js";
import { healthyRetrievalComponents, usedDerivedRetrieval } from "../diagnostics.js";
import type { ReadScope, ReadScopeInput, SingleScopeInput } from "../payload.js";
import type { CapturesClient, CreateCaptureData, CreateCaptureInput } from "../resources/captures.js";
import type { BuildContextInput, BuildDigestInput, ContextClient } from "../resources/context.js";
import type { FactsClient, RememberFactInput } from "../resources/facts.js";
import type { ApiEnvelope, FactRecord, JsonObject, SourceRef } from "../types.js";

export interface MemoryWorkflowResources {
  readonly captures: CapturesClient;
  readonly context: ContextClient;
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

function optional<TKey extends string, TValue>(
  key: TKey,
  value: TValue | undefined,
): { readonly [K in TKey]?: TValue } {
  return value === undefined ? {} : { [key]: value } as { readonly [K in TKey]: TValue };
}
