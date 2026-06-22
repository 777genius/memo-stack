import type {
  CheckFullMemoryReadinessInput,
  RunMemorySummaryLoopInput,
} from "./memory.js";
import type { MemoryBriefQualityPolicy } from "./memory-brief-quality.js";
import {
  MEMORY_QUALITY_PRESETS,
  type MemoryQualityPreset,
  type MemoryQualityPresetName,
} from "./memory-quality-presets.js";
import type { MemorySummaryLoopPolicy } from "./memory-summary-loop.js";

export type MemorySummaryLoopPlanPreset = MemoryQualityPresetName | MemoryQualityPreset;

export interface MemorySummaryLoopPlanOptions {
  readonly preset?: MemorySummaryLoopPlanPreset;
  readonly qualityPolicy?: MemoryBriefQualityPolicy;
  readonly summaryPolicy?: MemorySummaryLoopPolicy;
}

export interface MemorySummaryLoopPlan {
  readonly preset: MemoryQualityPreset;
  readonly input: RunMemorySummaryLoopInput;
  readonly policy: MemorySummaryLoopPolicy;
}

export function createMemorySummaryLoopPlan(
  input: RunMemorySummaryLoopInput,
  options: MemorySummaryLoopPlanOptions = {},
): MemorySummaryLoopPlan {
  const preset = resolveMemorySummaryLoopPreset(options.preset);
  const policy = freezePolicy(mergePolicy(preset.summaryLoop, options.summaryPolicy));
  const qualityPolicy = freezePolicy(mergePolicy(preset.brief, input.qualityPolicy, options.qualityPolicy));
  const brief = freezePolicy({
    ...input.brief,
    ...(qualityPolicy.requireSearch === true ? { includeSearch: true } : {}),
    ...(qualityPolicy.requireDigest === true ? { includeDigest: true } : {}),
  });
  const readiness = plannedReadiness(preset, policy, brief, input.readiness);
  const outboxDrain = plannedOutboxDrain(policy, input.outboxDrain);

  return Object.freeze({
    preset,
    policy,
    input: Object.freeze({
      ...input,
      brief,
      qualityPolicy,
      ...(readiness === undefined ? {} : { readiness }),
      ...(outboxDrain === undefined ? {} : { outboxDrain }),
    }),
  });
}

function resolveMemorySummaryLoopPreset(
  preset: MemorySummaryLoopPlanPreset | undefined,
): MemoryQualityPreset {
  return typeof preset === "string" || preset === undefined
    ? MEMORY_QUALITY_PRESETS[preset ?? "durable"]
    : preset;
}

function plannedReadiness(
  preset: MemoryQualityPreset,
  policy: MemorySummaryLoopPolicy,
  brief: RunMemorySummaryLoopInput["brief"],
  existing: RunMemorySummaryLoopInput["readiness"],
): RunMemorySummaryLoopInput["readiness"] {
  if (policy.requireReadiness !== true) {
    return existing ?? false;
  }

  const defaults = preset.name === "full" ? fullReadiness(brief) : durableReadiness();
  return typeof existing === "object"
    ? freezePolicy({ ...defaults, ...existing })
    : defaults;
}

function durableReadiness(): CheckFullMemoryReadinessInput {
  return freezePolicy({
    requiredAdapters: [],
    requiredRetrieval: [],
    requireDerivedRetrieval: false,
    assertReady: true,
  });
}

function fullReadiness(brief: RunMemorySummaryLoopInput["brief"]): CheckFullMemoryReadinessInput {
  return freezePolicy({
    ...briefReadinessScope(brief),
    query: brief.query,
    includeContextProbe: true,
    includeSearchProbe: true,
    ...(brief.tokenBudget !== undefined ? { tokenBudget: brief.tokenBudget } : {}),
    ...(brief.maxFacts !== undefined ? { maxFacts: brief.maxFacts } : {}),
    ...(brief.maxChunks !== undefined ? { maxChunks: brief.maxChunks } : {}),
    ...(brief.maxEvidenceItems !== undefined ? { maxEvidenceItems: brief.maxEvidenceItems } : {}),
    ...(brief.consistencyMode !== undefined ? { consistencyMode: brief.consistencyMode } : {}),
    ...(brief.includeStale !== undefined ? { includeStale: brief.includeStale } : {}),
    requiredAdapters: ["qdrant", "graphiti"],
    requiredRetrieval: ["vector", "graph"],
    requireDerivedRetrieval: true,
    assertReady: true,
  });
}

function briefReadinessScope(brief: RunMemorySummaryLoopInput["brief"]): CheckFullMemoryReadinessInput {
  return {
    ...(brief.readScope !== undefined ? { readScope: brief.readScope } : {}),
    ...(brief.spaceId !== undefined ? { spaceId: brief.spaceId } : {}),
    ...(brief.memoryScopeIds !== undefined ? { memoryScopeIds: brief.memoryScopeIds } : {}),
    ...(brief.threadId !== undefined ? { threadId: brief.threadId } : {}),
    ...(brief.spaceSlug !== undefined ? { spaceSlug: brief.spaceSlug } : {}),
    ...(brief.memoryScopeExternalRef !== undefined ? { memoryScopeExternalRef: brief.memoryScopeExternalRef } : {}),
    ...(brief.memoryScopeExternalRefs !== undefined ? { memoryScopeExternalRefs: brief.memoryScopeExternalRefs } : {}),
    ...(brief.threadExternalRef !== undefined ? { threadExternalRef: brief.threadExternalRef } : {}),
  };
}

function plannedOutboxDrain(
  policy: MemorySummaryLoopPolicy,
  existing: RunMemorySummaryLoopInput["outboxDrain"],
): RunMemorySummaryLoopInput["outboxDrain"] {
  if (policy.requireOutboxDrain !== true) {
    return existing;
  }
  const defaults = { throwOnFailure: true };
  return typeof existing === "object"
    ? freezePolicy({ ...defaults, ...existing })
    : Object.freeze(defaults);
}

function mergePolicy<TPolicy extends object>(
  ...policies: readonly (TPolicy | undefined)[]
): TPolicy {
  return Object.assign({}, ...policies.filter((policy): policy is TPolicy => policy !== undefined));
}

function freezePolicy<TPolicy extends object>(policy: TPolicy): TPolicy {
  const copy = { ...policy } as Record<string, unknown>;
  for (const [key, value] of Object.entries(copy)) {
    copy[key] = Array.isArray(value) ? Object.freeze([...value]) : value;
  }

  return Object.freeze(copy) as TPolicy;
}
