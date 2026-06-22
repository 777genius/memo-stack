import type { JsonObject, QueryParams } from "./types.js";

type ScopeValue = string | readonly string[] | undefined | null;

export interface SingleScopeInput {
  readonly spaceId?: string;
  readonly memoryScopeId?: string;
  readonly threadId?: string;
  readonly spaceSlug?: string;
  readonly memoryScopeExternalRef?: string;
  readonly threadExternalRef?: string;
}

export interface ReadScopeInput {
  readonly spaceId?: string;
  readonly memoryScopeIds?: readonly string[];
  readonly threadId?: string;
  readonly spaceSlug?: string;
  readonly memoryScopeExternalRef?: string;
  readonly memoryScopeExternalRefs?: readonly string[];
  readonly threadExternalRef?: string;
}

export class MemoryScope {
  private constructor(readonly value: SingleScopeInput) {}

  static canonical(input: {
    readonly spaceId: string;
    readonly memoryScopeId: string;
    readonly threadId?: string;
  }): MemoryScope {
    return new MemoryScope(input);
  }

  static external(input: {
    readonly spaceSlug: string;
    readonly memoryScopeExternalRef: string;
    readonly threadExternalRef?: string;
  }): MemoryScope {
    return new MemoryScope(input);
  }

  toPayload(): JsonObject {
    const payload = singleScopePayload(this.value);
    validateSingleScopePayload(payload);
    return payload;
  }
}

export class ReadScope {
  private constructor(readonly value: ReadScopeInput) {}

  static canonical(input: {
    readonly spaceId: string;
    readonly memoryScopeIds: readonly string[];
    readonly threadId?: string;
  }): ReadScope {
    return new ReadScope(input);
  }

  static external(input: {
    readonly spaceSlug: string;
    readonly memoryScopeExternalRef?: string;
    readonly memoryScopeExternalRefs?: readonly string[];
    readonly threadExternalRef?: string;
  }): ReadScope {
    return new ReadScope(input);
  }

  toPayload(): JsonObject {
    const payload = readScopePayload(this.value);
    validateReadScopePayload(payload);
    return payload;
  }
}

export function withoutUndefined<T extends Record<string, unknown>>(values: T): JsonObject {
  return Object.fromEntries(
    Object.entries(values).filter(([, value]) => value !== undefined && value !== null),
  ) as JsonObject;
}

export function singleScopePayload(input: SingleScopeInput): JsonObject {
  return toApiKeys({
    spaceId: input.spaceId,
    memoryScopeId: input.memoryScopeId,
    threadId: input.threadId,
    spaceSlug: input.spaceSlug,
    memoryScopeExternalRef: input.memoryScopeExternalRef,
    threadExternalRef: input.threadExternalRef,
  });
}

export function readScopePayload(input: ReadScopeInput): JsonObject {
  return toApiKeys({
    spaceId: input.spaceId,
    memoryScopeIds: input.memoryScopeIds,
    threadId: input.threadId,
    spaceSlug: input.spaceSlug,
    memoryScopeExternalRef: input.memoryScopeExternalRef,
    memoryScopeExternalRefs: input.memoryScopeExternalRefs,
    threadExternalRef: input.threadExternalRef,
  });
}

export function scopeQuery(input: SingleScopeInput): QueryParams {
  return singleScopePayload(input) as QueryParams;
}

export function validateSingleScopePayload(payload: JsonObject): void {
  const canonical = hasAny(payload, ["space_id", "memory_scope_id", "thread_id"]);
  const external = hasAny(payload, ["space_slug", "memory_scope_external_ref", "thread_external_ref"]);
  if (canonical && external) {
    throw new ValueError("Use either canonical ids or external refs, not both");
  }
  if (canonical && (!payload.space_id || !payload.memory_scope_id)) {
    throw new ValueError("spaceId and memoryScopeId are required with canonical scope");
  }
}

export function validateReadScopePayload(payload: JsonObject): void {
  const canonical = hasAny(payload, ["space_id", "memory_scope_ids", "thread_id"]);
  const external = hasAny(payload, [
    "space_slug",
    "memory_scope_external_ref",
    "memory_scope_external_refs",
    "thread_external_ref",
  ]);
  if (canonical && external) {
    throw new ValueError("Use either canonical ids or external refs, not both");
  }
  if (canonical && !payload.space_id) {
    throw new ValueError("spaceId is required with canonical read scope");
  }
  if (external && !payload.space_slug) {
    throw new ValueError("spaceSlug is required with external read scope");
  }
}

export class ValueError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ValueError";
  }
}

function hasAny(payload: JsonObject, keys: readonly string[]): boolean {
  return keys.some((key) => {
    const value = payload[key];
    return Array.isArray(value) ? value.length > 0 : value !== undefined && value !== null && value !== "";
  });
}

function toApiKeys(input: Record<string, ScopeValue>): JsonObject {
  return withoutUndefined({
    space_id: input.spaceId,
    memory_scope_id: input.memoryScopeId,
    memory_scope_ids: input.memoryScopeIds,
    thread_id: input.threadId,
    space_slug: input.spaceSlug,
    memory_scope_external_ref: input.memoryScopeExternalRef,
    memory_scope_external_refs: input.memoryScopeExternalRefs,
    thread_external_ref: input.threadExternalRef,
  }) as JsonObject;
}
