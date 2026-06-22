import type { RequestControls } from "../client.js";
import type { SingleScopeInput } from "../payload.js";
import type { JsonObject, SourceRef } from "../types.js";
import type {
  RecordSourceEvidenceBatchInput,
  RecordSourceEvidenceCaptureOptions,
  RecordSourceEvidenceDocumentOptions,
  RecordSourceEvidenceEpisodeOptions,
  RecordSourceEvidenceFactOptions,
  RecordSourceEvidenceInput,
  RecordSourceEvidenceLinkSuggestionOptions,
} from "./memory-source-evidence.js";
import {
  mergeWorkflowControls,
  optional,
  requiredWorkflowText,
  singleScopeInput,
  type WorkflowStepOptions,
} from "./workflow-helpers.js";

export interface MemorySourceEvidenceFinding extends SingleScopeInput, RequestControls {
  readonly sourceAgent?: string;
  readonly sourceType?: string;
  readonly sourceId: string;
  readonly title?: string;
  readonly text?: string;
  readonly url?: string;
  readonly occurredAt?: string;
  readonly idempotencyKey?: string;
  readonly sourceRefs?: readonly SourceRef[];
  readonly metadata?: JsonObject;
  readonly document?: WorkflowStepOptions<RecordSourceEvidenceDocumentOptions>;
  readonly episode?: WorkflowStepOptions<RecordSourceEvidenceEpisodeOptions>;
  readonly capture?: WorkflowStepOptions<RecordSourceEvidenceCaptureOptions>;
  readonly fact?: WorkflowStepOptions<RecordSourceEvidenceFactOptions>;
  readonly linkSuggestions?: WorkflowStepOptions<RecordSourceEvidenceLinkSuggestionOptions>;
}

export interface CreateMemorySourceEvidencePlanInput extends SingleScopeInput, RequestControls {
  readonly sourceAgent: string;
  readonly sourceType?: string;
  readonly findings: readonly MemorySourceEvidenceFinding[];
  readonly idempotencyKeyPrefix?: string;
  readonly sourceRefs?: readonly SourceRef[];
  readonly metadata?: JsonObject;
  readonly concurrency?: number;
  readonly continueOnError?: boolean;
  readonly document?: WorkflowStepOptions<RecordSourceEvidenceDocumentOptions>;
  readonly episode?: WorkflowStepOptions<RecordSourceEvidenceEpisodeOptions>;
  readonly capture?: WorkflowStepOptions<RecordSourceEvidenceCaptureOptions>;
  readonly fact?: WorkflowStepOptions<RecordSourceEvidenceFactOptions>;
  readonly linkSuggestions?: WorkflowStepOptions<RecordSourceEvidenceLinkSuggestionOptions>;
}

export interface MemorySourceEvidencePlanSummary {
  readonly total: number;
  readonly sourceTypes: readonly string[];
  readonly idempotencyKeys: readonly string[];
}

export interface MemorySourceEvidencePlan {
  readonly items: readonly RecordSourceEvidenceInput[];
  readonly batch: RecordSourceEvidenceBatchInput;
  readonly sourceRefs: readonly SourceRef[];
  readonly summary: MemorySourceEvidencePlanSummary;
}

export function createMemorySourceEvidencePlan(
  input: CreateMemorySourceEvidencePlanInput,
): MemorySourceEvidencePlan {
  const sourceAgent = requiredWorkflowText(
    input.sourceAgent,
    "createMemorySourceEvidencePlan requires sourceAgent",
  );
  const idempotencyKeyPrefix = input.idempotencyKeyPrefix ?? "source-evidence";
  const items = freezeArray(input.findings.map((finding) =>
    evidenceFindingItem(input, finding, sourceAgent, idempotencyKeyPrefix)
  ));
  const sourceRefs = freezeArray(uniqueSourceRefs(items.flatMap((item) => item.sourceRefs ?? [])));
  const batch = Object.freeze({
    ...mergeWorkflowControls(input, {}),
    items,
    ...optional("concurrency", input.concurrency),
    ...optional("continueOnError", input.continueOnError),
  });

  return Object.freeze({
    items,
    batch,
    sourceRefs,
    summary: Object.freeze({
      total: items.length,
      sourceTypes: freezeArray(uniqueStrings(items.map((item) => item.sourceType))),
      idempotencyKeys: freezeArray(items.map((item) => item.idempotencyKey)),
    }),
  });
}

function evidenceFindingItem(
  input: CreateMemorySourceEvidencePlanInput,
  finding: MemorySourceEvidenceFinding,
  sourceAgent: string,
  idempotencyKeyPrefix: string,
): RecordSourceEvidenceInput {
  const sourceType = requiredWorkflowText(
    finding.sourceType ?? input.sourceType,
    "source evidence finding requires sourceType or plan sourceType",
  );
  const sourceId = requiredWorkflowText(finding.sourceId, "source evidence finding requires sourceId");
  const text = requiredWorkflowText(
    finding.text ?? finding.title,
    "source evidence finding requires text or title",
  );
  const sourceRefs = freezeArray(uniqueSourceRefs([
    { source_type: sourceType, source_id: sourceId },
    ...(input.sourceRefs ?? []),
    ...(finding.sourceRefs ?? []),
  ]));
  const controls = mergeWorkflowControls({}, finding);
  const metadata = evidenceMetadata(input.metadata, finding);

  return Object.freeze({
    ...singleScopeInput(input),
    ...singleScopeInput(finding),
    ...controls,
    sourceAgent: finding.sourceAgent ?? sourceAgent,
    sourceType,
    sourceId,
    text,
    title: finding.title ?? text,
    idempotencyKey: evidenceIdempotencyKey(idempotencyKeyPrefix, sourceType, sourceId, finding),
    sourceRefs,
    ...optional("occurredAt", finding.occurredAt),
    ...optional("metadata", metadata),
    ...optional("document", finding.document ?? input.document),
    ...optional("episode", finding.episode ?? input.episode),
    ...optional("capture", finding.capture ?? input.capture),
    ...optional("fact", finding.fact ?? input.fact),
    ...optional("linkSuggestions", finding.linkSuggestions ?? input.linkSuggestions),
  });
}

function evidenceIdempotencyKey(
  prefix: string,
  sourceType: string,
  sourceId: string,
  finding: MemorySourceEvidenceFinding,
): string {
  if (finding.idempotencyKey !== undefined) {
    return requiredWorkflowText(finding.idempotencyKey, "source evidence idempotencyKey cannot be empty");
  }

  const idempotencyKeyPrefix = requiredWorkflowText(
    prefix,
    "source evidence idempotencyKeyPrefix cannot be empty",
  );
  return `${idempotencyKeyPrefix}:${sourceType}:${sourceId}`;
}

function evidenceMetadata(
  baseMetadata: JsonObject | undefined,
  finding: MemorySourceEvidenceFinding,
): JsonObject | undefined {
  if (baseMetadata === undefined && finding.metadata === undefined && finding.url === undefined) {
    return undefined;
  }

  return Object.freeze({
    ...baseMetadata,
    ...finding.metadata,
    ...optional("url", finding.url),
  });
}

function uniqueSourceRefs(sourceRefs: readonly SourceRef[]): readonly SourceRef[] {
  const seen = new Set<string>();
  const result: SourceRef[] = [];
  for (const sourceRef of sourceRefs) {
    const key = `${sourceRef.source_type}:${sourceRef.source_id}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push(Object.freeze({ ...sourceRef }));
  }
  return result;
}

function uniqueStrings(values: readonly string[]): readonly string[] {
  return [...new Set(values)];
}

function freezeArray<TValue>(values: readonly TValue[]): readonly TValue[] {
  return Object.freeze([...values]);
}
