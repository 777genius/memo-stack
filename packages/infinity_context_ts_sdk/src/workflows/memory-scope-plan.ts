import type { JsonObject } from "../types.js";
import type {
  EnsureMemoryScopeInput,
  EnsureMemoryTopologyInput,
  EnsureMemoryUserInput,
} from "./memory-topology.js";
import { requiredWorkflowText } from "./workflow-helpers.js";

export type MemoryScopePlanKind = "workspace" | "user" | "topic" | "source";

export interface MemoryScopePlanUser {
  readonly externalRef: string;
  readonly displayName?: string;
  readonly email?: string;
  readonly metadata?: JsonObject;
  readonly role?: string;
  readonly includeInReadScope?: boolean;
}

export interface MemoryScopePlanTopic {
  readonly slug: string;
  readonly name?: string;
  readonly includeInReadScope?: boolean;
}

export interface MemoryScopePlanSource {
  readonly externalRef?: string;
  readonly sourceType?: string;
  readonly sourceId?: string;
  readonly name?: string;
  readonly includeInReadScope?: boolean;
}

export interface CreateMemoryScopePlanInput {
  readonly spaceSlug: string;
  readonly spaceName?: string;
  readonly workspaceExternalRef?: string;
  readonly workspaceName?: string;
  readonly includeWorkspace?: boolean;
  readonly users?: readonly MemoryScopePlanUser[];
  readonly topics?: readonly MemoryScopePlanTopic[];
  readonly sources?: readonly MemoryScopePlanSource[];
  readonly threadExternalRef?: string;
  readonly createMemberships?: boolean;
}

export interface MemoryScopePlanEntry extends EnsureMemoryScopeInput {
  readonly kind: MemoryScopePlanKind;
}

export interface MemoryScopePlan {
  readonly spaceSlug: string;
  readonly spaceName: string;
  readonly memoryScopes: readonly MemoryScopePlanEntry[];
  readonly users: readonly EnsureMemoryUserInput[];
  readonly readScope: {
    readonly spaceSlug: string;
    readonly memoryScopeExternalRefs: readonly string[];
    readonly threadExternalRef?: string;
  };
  readonly topology: EnsureMemoryTopologyInput;
}

export function createMemoryScopePlan(input: CreateMemoryScopePlanInput): MemoryScopePlan {
  const spaceSlug = requiredWorkflowText(input.spaceSlug, "createMemoryScopePlan requires spaceSlug");
  const spaceName = input.spaceName ?? spaceSlug;
  const memoryScopes = freezeArray([
    ...(input.includeWorkspace ?? true ? [workspaceScope(input)] : []),
    ...(input.users ?? []).map(userScope),
    ...(input.topics ?? []).map(topicScope),
    ...(input.sources ?? []).map(sourceScope),
  ]);
  const users = freezeArray((input.users ?? []).map(topologyUser));
  const readScopeRefs = freezeArray(memoryScopes
    .filter((scope) => scopeIncludedInReadScope(scope, input))
    .map((scope) => scope.externalRef));
  const readScope = Object.freeze({
    spaceSlug,
    memoryScopeExternalRefs: readScopeRefs,
    ...(input.threadExternalRef !== undefined ? { threadExternalRef: input.threadExternalRef } : {}),
  });
  const topology = Object.freeze({
    spaceSlug,
    spaceName,
    memoryScopes,
    ...(users.length > 0 ? { users } : {}),
    ...(users.length > 0 || input.createMemberships !== undefined
      ? { createMemberships: input.createMemberships ?? true }
      : {}),
  });

  return Object.freeze({
    spaceSlug,
    spaceName,
    memoryScopes,
    users,
    readScope,
    topology,
  });
}

function workspaceScope(input: CreateMemoryScopePlanInput): MemoryScopePlanEntry {
  const externalRef = input.workspaceExternalRef ?? "workspace-global";
  return freezeEntry({
    kind: "workspace",
    externalRef,
    name: input.workspaceName ?? "Workspace global memory",
  });
}

function userScope(input: MemoryScopePlanUser): MemoryScopePlanEntry {
  const externalRef = scopedExternalRef("user", input.externalRef, "user scope requires externalRef");
  return freezeEntry({
    kind: "user",
    externalRef,
    name: `${input.displayName ?? input.externalRef} memory`,
  });
}

function topicScope(input: MemoryScopePlanTopic): MemoryScopePlanEntry {
  const externalRef = scopedExternalRef("topic", input.slug, "topic scope requires slug");
  return freezeEntry({
    kind: "topic",
    externalRef,
    name: input.name ?? `${input.slug} topic memory`,
  });
}

function sourceScope(input: MemoryScopePlanSource): MemoryScopePlanEntry {
  const externalRef = input.externalRef ?? [
    "source",
    requiredWorkflowText(input.sourceType, "source scope requires sourceType or externalRef"),
    requiredWorkflowText(input.sourceId, "source scope requires sourceId or externalRef"),
  ].join(":");
  return freezeEntry({
    kind: "source",
    externalRef,
    name: input.name ?? `${externalRef} memory`,
  });
}

function topologyUser(input: MemoryScopePlanUser): EnsureMemoryUserInput {
  const externalRef = scopedExternalRef("user", input.externalRef, "topology user requires externalRef");
  return Object.freeze({
    externalRef,
    displayName: input.displayName ?? input.externalRef,
    ...(input.email !== undefined ? { email: input.email } : {}),
    ...(input.metadata !== undefined ? { metadata: input.metadata } : {}),
    ...(input.role !== undefined ? { role: input.role } : {}),
  });
}

function scopedExternalRef(prefix: string, value: string, message: string): string {
  const text = requiredWorkflowText(value, message);
  return text.startsWith(`${prefix}:`) ? text : `${prefix}:${text}`;
}

function scopeIncludedInReadScope(
  scope: MemoryScopePlanEntry,
  input: CreateMemoryScopePlanInput,
): boolean {
  if (scope.kind === "workspace") {
    return input.includeWorkspace ?? true;
  }
  if (scope.kind === "user") {
    return (input.users ?? []).some((user) =>
      scopedExternalRef("user", user.externalRef, "user scope requires externalRef") === scope.externalRef &&
      user.includeInReadScope !== false
    );
  }
  if (scope.kind === "topic") {
    return (input.topics ?? []).some((topic) =>
      scopedExternalRef("topic", topic.slug, "topic scope requires slug") === scope.externalRef &&
      topic.includeInReadScope !== false
    );
  }
  return (input.sources ?? []).some((source) =>
    sourceScope(source).externalRef === scope.externalRef && source.includeInReadScope !== false
  );
}

function freezeEntry(entry: MemoryScopePlanEntry): MemoryScopePlanEntry {
  return Object.freeze(entry);
}

function freezeArray<TValue>(values: readonly TValue[]): readonly TValue[] {
  return Object.freeze([...values]);
}
