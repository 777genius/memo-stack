import type { RequestControls } from "../client.js";
import type {
  BuildMemoryBriefInput,
  RunMemorySummaryLoopInput,
} from "./memory.js";
import type { MemoryBriefQualityPolicy } from "./memory-brief-quality.js";
import {
  createMemoryScopePlan,
  type CreateMemoryScopePlanInput,
  type MemoryScopePlan,
  type MemoryScopePlanEntry,
} from "./memory-scope-plan.js";
import type { MemorySummaryLoopPolicy } from "./memory-summary-loop.js";
import {
  createMemorySummaryLoopPlan,
  type MemorySummaryLoopPlan,
  type MemorySummaryLoopPlanOptions,
  type MemorySummaryLoopPlanPreset,
} from "./memory-summary-loop-plan.js";
import {
  createMemorySourceEvidencePlan,
  type CreateMemorySourceEvidencePlanInput,
  type MemorySourceEvidenceFinding,
  type MemorySourceEvidencePlan,
} from "./memory-source-evidence-plan.js";
import {
  mergeWorkflowControls,
  optional,
  requiredWorkflowText,
} from "./workflow-helpers.js";

export type MemoryIngestionLoopScopeOptions = Omit<
  CreateMemoryScopePlanInput,
  "spaceSlug" | "spaceName" | "threadExternalRef"
>;

export type MemoryIngestionLoopSourceEvidenceOptions = Omit<
  CreateMemorySourceEvidencePlanInput,
  "sourceAgent" | "findings" | "spaceId" | "spaceSlug" | "memoryScopeId" | "threadId" | "threadExternalRef"
>;

export type MemoryIngestionLoopBriefOptions = Omit<
  BuildMemoryBriefInput,
  | "query"
  | "topic"
  | "readScope"
  | "spaceId"
  | "memoryScopeIds"
  | "threadId"
  | "spaceSlug"
  | "memoryScopeExternalRef"
  | "memoryScopeExternalRefs"
  | "threadExternalRef"
> & {
  readonly memoryScopeExternalRefs?: readonly string[];
};

export interface CreateMemoryIngestionLoopPlanInput extends RequestControls {
  readonly spaceSlug: string;
  readonly spaceName?: string;
  readonly sourceAgent: string;
  readonly query: string;
  readonly topic?: string;
  readonly threadExternalRef?: string;
  readonly findings: readonly MemorySourceEvidenceFinding[];
  readonly scope?: MemoryIngestionLoopScopeOptions;
  readonly sourceEvidence?: MemoryIngestionLoopSourceEvidenceOptions;
  readonly brief?: MemoryIngestionLoopBriefOptions;
  readonly preset?: MemorySummaryLoopPlanPreset;
  readonly qualityPolicy?: MemoryBriefQualityPolicy;
  readonly summaryPolicy?: MemorySummaryLoopPolicy;
  readonly readiness?: RunMemorySummaryLoopInput["readiness"];
  readonly outboxDrain?: RunMemorySummaryLoopInput["outboxDrain"];
  readonly stopOnSourceEvidenceFailure?: boolean;
}

export interface MemoryIngestionLoopReadScope {
  readonly spaceSlug: string;
  readonly memoryScopeExternalRefs: readonly string[];
  readonly threadExternalRef?: string;
}

export interface MemoryIngestionLoopPlanSummary {
  readonly spaceSlug: string;
  readonly memoryScopeCount: number;
  readonly findingCount: number;
  readonly sourceTypes: readonly string[];
  readonly readScopeExternalRefs: readonly string[];
}

export interface MemoryIngestionLoopPlan {
  readonly scope: MemoryScopePlan;
  readonly sourceEvidence: MemorySourceEvidencePlan;
  readonly summaryLoop: MemorySummaryLoopPlan;
  readonly input: RunMemorySummaryLoopInput;
  readonly policy: MemorySummaryLoopPolicy;
  readonly readScope: MemoryIngestionLoopReadScope;
  readonly summary: MemoryIngestionLoopPlanSummary;
}

export function createMemoryIngestionLoopPlan(
  input: CreateMemoryIngestionLoopPlanInput,
): MemoryIngestionLoopPlan {
  const spaceSlug = requiredWorkflowText(input.spaceSlug, "createMemoryIngestionLoopPlan requires spaceSlug");
  const sourceAgent = requiredWorkflowText(
    input.sourceAgent,
    "createMemoryIngestionLoopPlan requires sourceAgent",
  );
  const query = requiredWorkflowText(input.query, "createMemoryIngestionLoopPlan requires query");
  const scope = createMemoryScopePlan({
    ...(input.scope ?? {}),
    spaceSlug,
    ...optional("spaceName", input.spaceName),
    ...optional("threadExternalRef", input.threadExternalRef),
  });
  const readScope = ingestionLoopReadScope(scope, input);
  const sourceEvidence = createMemorySourceEvidencePlan(sourceEvidenceInput(input, scope, spaceSlug, sourceAgent));
  const summaryLoop = createMemorySummaryLoopPlan(summaryLoopInput(input, scope, sourceEvidence, readScope, query), {
    ...optional("preset", input.preset),
    ...optional("summaryPolicy", input.summaryPolicy),
  } satisfies MemorySummaryLoopPlanOptions);

  return Object.freeze({
    scope,
    sourceEvidence,
    summaryLoop,
    input: summaryLoop.input,
    policy: summaryLoop.policy,
    readScope,
    summary: Object.freeze({
      spaceSlug,
      memoryScopeCount: scope.memoryScopes.length,
      findingCount: sourceEvidence.summary.total,
      sourceTypes: sourceEvidence.summary.sourceTypes,
      readScopeExternalRefs: readScope.memoryScopeExternalRefs,
    }),
  });
}

function sourceEvidenceInput(
  input: CreateMemoryIngestionLoopPlanInput,
  scope: MemoryScopePlan,
  spaceSlug: string,
  sourceAgent: string,
): CreateMemorySourceEvidencePlanInput {
  const sourceEvidence = input.sourceEvidence ?? {};
  return {
    ...defaultSourceEvidenceScope(scope, sourceEvidence),
    ...sourceEvidence,
    ...mergeWorkflowControls(input, sourceEvidence),
    spaceSlug,
    ...optional("threadExternalRef", input.threadExternalRef),
    sourceAgent,
    findings: input.findings,
    idempotencyKeyPrefix: sourceEvidence.idempotencyKeyPrefix ?? input.threadExternalRef ?? "source-evidence",
  };
}

function summaryLoopInput(
  input: CreateMemoryIngestionLoopPlanInput,
  scope: MemoryScopePlan,
  sourceEvidence: MemorySourceEvidencePlan,
  readScope: MemoryIngestionLoopReadScope,
  query: string,
): RunMemorySummaryLoopInput {
  return Object.freeze({
    ...mergeWorkflowControls(input, {}),
    topology: scope.topology,
    sourceEvidence: sourceEvidence.batch,
    ...optional("readiness", input.readiness),
    ...optional("outboxDrain", input.outboxDrain),
    brief: ingestionLoopBrief(input, readScope, query),
    ...optional("qualityPolicy", input.qualityPolicy),
    ...optional("stopOnSourceEvidenceFailure", input.stopOnSourceEvidenceFailure),
  });
}

function ingestionLoopBrief(
  input: CreateMemoryIngestionLoopPlanInput,
  readScope: MemoryIngestionLoopReadScope,
  query: string,
): BuildMemoryBriefInput {
  return Object.freeze({
    ...(input.brief ?? {}),
    ...readScope,
    query,
    topic: input.topic ?? query,
  });
}

function ingestionLoopReadScope(
  scope: MemoryScopePlan,
  input: CreateMemoryIngestionLoopPlanInput,
): MemoryIngestionLoopReadScope {
  return Object.freeze({
    spaceSlug: scope.spaceSlug,
    memoryScopeExternalRefs: freezeArray(uniqueStrings([
      ...scope.readScope.memoryScopeExternalRefs,
      ...(input.brief?.memoryScopeExternalRefs ?? []),
    ])),
    ...optional("threadExternalRef", input.threadExternalRef ?? scope.readScope.threadExternalRef),
  });
}

function defaultSourceEvidenceScope(
  scope: MemoryScopePlan,
  input: MemoryIngestionLoopSourceEvidenceOptions,
): Pick<CreateMemorySourceEvidencePlanInput, "memoryScopeExternalRef"> {
  if (input.memoryScopeExternalRef !== undefined) {
    return {};
  }

  return {
    memoryScopeExternalRef: defaultEvidenceScopeRef(scope),
  };
}

function defaultEvidenceScopeRef(scope: MemoryScopePlan): string {
  return preferredScope(scope.memoryScopes, "source")
    ?? preferredScope(scope.memoryScopes, "topic")
    ?? preferredScope(scope.memoryScopes, "workspace")
    ?? requiredWorkflowText(scope.readScope.memoryScopeExternalRefs[0], "memory ingestion loop requires a read scope");
}

function preferredScope(
  scopes: readonly MemoryScopePlanEntry[],
  kind: MemoryScopePlanEntry["kind"],
): string | undefined {
  return scopes.find((scope) => scope.kind === kind)?.externalRef;
}

function uniqueStrings(values: readonly string[]): readonly string[] {
  return [...new Set(values)];
}

function freezeArray<TValue>(values: readonly TValue[]): readonly TValue[] {
  return Object.freeze([...values]);
}
