import type { RequestControls } from "../client.js";
import { ValueError } from "../payload.js";
import type { SourceRef } from "../types.js";
import type {
  BuildMemoryBriefInput,
  SeedMemoryAndBuildBriefInput,
  SeedMemoryFactInput,
} from "./memory.js";
import {
  createMemoryScopePlan,
  type CreateMemoryScopePlanInput,
  type MemoryScopePlan,
  type MemoryScopePlanEntry,
} from "./memory-scope-plan.js";
import {
  mergeWorkflowControls,
  optional,
  requiredWorkflowText,
} from "./workflow-helpers.js";

export type MemoryPreferenceBriefScopeOptions = Omit<
  CreateMemoryScopePlanInput,
  "spaceSlug" | "spaceName" | "threadExternalRef"
>;

export type MemoryPreferenceBriefOptions = Omit<
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

export interface MemoryPreferenceSeed extends RequestControls {
  readonly text: string;
  readonly memoryScopeExternalRef?: string;
  readonly idempotencyKey?: string;
  readonly sourceRefs?: readonly SourceRef[];
  readonly kind?: string;
  readonly classification?: string;
  readonly category?: string;
  readonly tags?: readonly string[];
  readonly ttlPolicy?: string;
}

export interface CreateMemoryPreferenceBriefPlanInput extends RequestControls {
  readonly spaceSlug: string;
  readonly spaceName?: string;
  readonly query: string;
  readonly topic?: string;
  readonly threadExternalRef?: string;
  readonly preferences: readonly MemoryPreferenceSeed[];
  readonly scope?: MemoryPreferenceBriefScopeOptions;
  readonly defaultMemoryScopeExternalRef?: string;
  readonly idempotencyKeyPrefix?: string;
  readonly sourceType?: string;
  readonly sourceIdPrefix?: string;
  readonly topology?: SeedMemoryAndBuildBriefInput["topology"];
  readonly outboxDrain?: SeedMemoryAndBuildBriefInput["outboxDrain"];
  readonly brief?: MemoryPreferenceBriefOptions;
}

export interface MemoryPreferenceBriefReadScope {
  readonly spaceSlug: string;
  readonly memoryScopeExternalRefs: readonly string[];
  readonly threadExternalRef?: string;
}

export interface MemoryPreferenceBriefPlanSummary {
  readonly spaceSlug: string;
  readonly preferenceCount: number;
  readonly defaultMemoryScopeExternalRef: string;
  readonly readScopeExternalRefs: readonly string[];
  readonly idempotencyKeys: readonly string[];
}

export interface MemoryPreferenceBriefPlan {
  readonly scope: MemoryScopePlan;
  readonly facts: readonly SeedMemoryFactInput[];
  readonly input: SeedMemoryAndBuildBriefInput;
  readonly readScope: MemoryPreferenceBriefReadScope;
  readonly summary: MemoryPreferenceBriefPlanSummary;
}

export function createMemoryPreferenceBriefPlan(
  input: CreateMemoryPreferenceBriefPlanInput,
): MemoryPreferenceBriefPlan {
  const spaceSlug = requiredWorkflowText(input.spaceSlug, "createMemoryPreferenceBriefPlan requires spaceSlug");
  const query = requiredWorkflowText(input.query, "createMemoryPreferenceBriefPlan requires query");
  if (input.preferences.length > 100) {
    throw new ValueError("createMemoryPreferenceBriefPlan supports at most 100 preferences");
  }

  const scope = createMemoryScopePlan({
    ...(input.scope ?? {}),
    spaceSlug,
    ...optional("spaceName", input.spaceName),
    ...optional("threadExternalRef", input.threadExternalRef),
  });
  const defaultMemoryScopeExternalRef = input.defaultMemoryScopeExternalRef ?? defaultPreferenceScopeRef(scope);
  const idempotencyKeyPrefix = input.idempotencyKeyPrefix ?? `${spaceSlug}:preferences`;
  const sourceIdPrefix = input.sourceIdPrefix ?? idempotencyKeyPrefix;
  const facts = freezeArray(input.preferences.map((preference, index) =>
    preferenceFact(input, preference, defaultMemoryScopeExternalRef, idempotencyKeyPrefix, sourceIdPrefix, index)
  ));
  const readScope = preferenceReadScope(scope, input, facts, defaultMemoryScopeExternalRef);
  const topology = plannedTopology(input, scope);
  const outboxDrain = plannedOutboxDrain(input);
  const seedInput = Object.freeze({
    ...mergeWorkflowControls(input, {}),
    spaceSlug,
    memoryScopeExternalRef: defaultMemoryScopeExternalRef,
    ...optional("threadExternalRef", input.threadExternalRef),
    idempotencyKeyPrefix,
    sourceType: input.sourceType ?? "memory_preference",
    sourceIdPrefix,
    facts,
    ...optional("topology", topology),
    ...optional("outboxDrain", outboxDrain),
    brief: preferenceBrief(input, readScope, query),
  } satisfies SeedMemoryAndBuildBriefInput);

  return Object.freeze({
    scope,
    facts,
    input: seedInput,
    readScope,
    summary: Object.freeze({
      spaceSlug,
      preferenceCount: facts.length,
      defaultMemoryScopeExternalRef,
      readScopeExternalRefs: readScope.memoryScopeExternalRefs,
      idempotencyKeys: freezeArray(facts.map((fact) => fact.idempotencyKey ?? "")),
    }),
  });
}

function preferenceFact(
  input: CreateMemoryPreferenceBriefPlanInput,
  preference: MemoryPreferenceSeed,
  defaultMemoryScopeExternalRef: string,
  idempotencyKeyPrefix: string,
  sourceIdPrefix: string,
  index: number,
): SeedMemoryFactInput {
  const text = requiredWorkflowText(preference.text, "memory preference requires text");
  const idempotencyKey = preference.idempotencyKey ?? `${idempotencyKeyPrefix}:preference:${index}`;

  return Object.freeze({
    ...mergeWorkflowControls({}, preference),
    text,
    memoryScopeExternalRef: preference.memoryScopeExternalRef ?? defaultMemoryScopeExternalRef,
    idempotencyKey,
    sourceRefs: freezeArray(preference.sourceRefs ?? [{
      source_type: input.sourceType ?? "memory_preference",
      source_id: `${sourceIdPrefix}:preference:${index}`,
    }]),
    kind: preference.kind ?? "user_preference",
    classification: preference.classification ?? "internal",
    category: preference.category ?? "summary_preference",
    tags: freezeArray(preference.tags ?? ["preference", "summary"]),
    ttlPolicy: preference.ttlPolicy ?? "durable",
  });
}

function preferenceBrief(
  input: CreateMemoryPreferenceBriefPlanInput,
  readScope: MemoryPreferenceBriefReadScope,
  query: string,
): BuildMemoryBriefInput {
  return Object.freeze({
    ...(input.brief ?? {}),
    ...readScope,
    query,
    topic: input.topic ?? query,
  });
}

function preferenceReadScope(
  scope: MemoryScopePlan,
  input: CreateMemoryPreferenceBriefPlanInput,
  facts: readonly SeedMemoryFactInput[],
  defaultMemoryScopeExternalRef: string,
): MemoryPreferenceBriefReadScope {
  return Object.freeze({
    spaceSlug: scope.spaceSlug,
    memoryScopeExternalRefs: freezeArray(uniqueStrings([
      ...scope.readScope.memoryScopeExternalRefs,
      defaultMemoryScopeExternalRef,
      ...facts.map((fact) => fact.memoryScopeExternalRef ?? defaultMemoryScopeExternalRef),
      ...(input.brief?.memoryScopeExternalRefs ?? []),
    ])),
    ...optional("threadExternalRef", input.threadExternalRef ?? scope.readScope.threadExternalRef),
  });
}

function plannedTopology(
  input: CreateMemoryPreferenceBriefPlanInput,
  scope: MemoryScopePlan,
): SeedMemoryAndBuildBriefInput["topology"] {
  if (input.topology === undefined || input.topology === true) {
    return scope.topology;
  }
  return input.topology;
}

function plannedOutboxDrain(
  input: CreateMemoryPreferenceBriefPlanInput,
): SeedMemoryAndBuildBriefInput["outboxDrain"] {
  if (input.outboxDrain === undefined || input.outboxDrain === true) {
    return Object.freeze({ throwOnFailure: true });
  }
  return input.outboxDrain;
}

function defaultPreferenceScopeRef(scope: MemoryScopePlan): string {
  return preferredScope(scope.memoryScopes, "user")
    ?? preferredScope(scope.memoryScopes, "topic")
    ?? preferredScope(scope.memoryScopes, "workspace")
    ?? requiredWorkflowText(scope.readScope.memoryScopeExternalRefs[0], "memory preference plan requires a read scope");
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
