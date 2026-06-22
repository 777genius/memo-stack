import type { RequestExecutor } from "../client.js";
import { scopeQuery, withoutUndefined, ValueError, type SingleScopeInput } from "../payload.js";
import type { ApiEnvelope, JsonObject, SourceRef, SuggestionRecord } from "../types.js";

export type CreateSuggestionInput = {
  readonly candidateText: string;
  readonly safeReason: string;
  readonly kind?: string;
  readonly sourceRefs?: readonly SourceRef[];
  readonly trustLevel?: string;
  readonly confidence?: string;
  readonly targetFactId?: string;
  readonly targetFactVersion?: number;
  readonly operation?: string;
  readonly category?: string;
  readonly tags?: readonly string[];
  readonly ttlPolicy?: string;
  readonly expiresAt?: string;
  readonly expiryReason?: string;
  readonly createdFromCaptureId?: string;
  readonly candidateFingerprint?: string;
  readonly reviewPayload?: JsonObject;
  readonly autoApprove?: boolean;
};

export type CreateSuggestionsBatchItemInput = CreateSuggestionInput;

export interface CreateSuggestionsBatchData extends JsonObject {
  readonly created: number;
  readonly existing: number;
  readonly failed: number;
  readonly stopped: boolean;
  readonly results: readonly JsonObject[];
}

export interface ResolveSuggestionData extends JsonObject {
  readonly suggestion: SuggestionRecord;
  readonly fact?: JsonObject;
}

export class SuggestionsClient {
  constructor(private readonly http: RequestExecutor) {}

  createSuggestion(input: SingleScopeInput & CreateSuggestionInput): Promise<ApiEnvelope<SuggestionRecord>> {
    validateTargetFactVersion(input, "targetFactVersion");
    return this.http.request<ApiEnvelope<SuggestionRecord>>({
      method: "POST",
      path: "/v1/suggestions",
      json: withoutUndefined({
        ...scopeQuery(input),
        ...suggestionPayload(input),
      }) as JsonObject,
    });
  }

  createSuggestionsBatch(
    input: SingleScopeInput & {
      readonly items: readonly CreateSuggestionsBatchItemInput[];
      readonly continueOnError?: boolean;
    },
  ): Promise<ApiEnvelope<CreateSuggestionsBatchData>> {
    input.items.forEach((item, index) => {
      validateTargetFactVersion(item, `items[${index}].targetFactVersion`);
    });
    return this.http.request<ApiEnvelope<CreateSuggestionsBatchData>>({
      method: "POST",
      path: "/v1/suggestions/batch",
      json: withoutUndefined({
        ...scopeQuery(input),
        items: input.items.map((item) => suggestionPayload(item)),
        continue_on_error: input.continueOnError ?? false,
      }) as JsonObject,
    });
  }

  listSuggestions(input: SingleScopeInput & {
    readonly status?: string | null;
    readonly operation?: string;
    readonly category?: string;
    readonly tag?: string;
    readonly limit?: number;
  }): Promise<ApiEnvelope<SuggestionRecord[]>> {
    return this.http.request<ApiEnvelope<SuggestionRecord[]>>({
      method: "GET",
      path: "/v1/suggestions",
      params: withoutUndefined({
        ...scopeQuery(input),
        operation: input.operation,
        category: input.category,
        tag: input.tag,
        limit: input.limit ?? 100,
        status: input.status,
      }),
    });
  }

  approveSuggestion(
    suggestionId: string,
    input: { readonly reason?: string; readonly force?: boolean } = {},
  ): Promise<ApiEnvelope<JsonObject>> {
    return this.http.request<ApiEnvelope<JsonObject>>({
      method: "POST",
      path: `/v1/suggestions/${suggestionId}/approve`,
      json: withoutUndefined({ reason: input.reason, force: input.force ?? false }),
    });
  }

  resolveSuggestionConflict(
    suggestionId: string,
    input: {
      readonly action: "approve" | "reject" | "expire" | string;
      readonly reason?: string;
      readonly force?: boolean;
    },
  ): Promise<ApiEnvelope<ResolveSuggestionData>> {
    return this.http.request<ApiEnvelope<ResolveSuggestionData>>({
      method: "POST",
      path: `/v1/suggestions/${suggestionId}/resolve-conflict`,
      json: withoutUndefined({ action: input.action, reason: input.reason, force: input.force ?? false }),
    });
  }

  resolveDuplicateMerge(
    suggestionId: string,
    input: {
      readonly action: "approve" | "reject" | "expire" | string;
      readonly reason?: string;
      readonly force?: boolean;
    },
  ): Promise<ApiEnvelope<ResolveSuggestionData>> {
    return this.http.request<ApiEnvelope<ResolveSuggestionData>>({
      method: "POST",
      path: `/v1/suggestions/${suggestionId}/resolve-duplicate`,
      json: withoutUndefined({ action: input.action, reason: input.reason, force: input.force ?? false }),
    });
  }

  rejectSuggestion(suggestionId: string, input: { readonly reason?: string } = {}): Promise<ApiEnvelope<JsonObject>> {
    return this.http.request<ApiEnvelope<JsonObject>>({
      method: "POST",
      path: `/v1/suggestions/${suggestionId}/reject`,
      json: withoutUndefined({ reason: input.reason }),
    });
  }

  expireSuggestion(suggestionId: string, input: { readonly reason?: string } = {}): Promise<ApiEnvelope<JsonObject>> {
    return this.http.request<ApiEnvelope<JsonObject>>({
      method: "POST",
      path: `/v1/suggestions/${suggestionId}/expire`,
      json: withoutUndefined({ reason: input.reason }),
    });
  }

  reviewSuggestionsBatch(
    items: readonly JsonObject[],
    input: { readonly continueOnError?: boolean } = {},
  ): Promise<ApiEnvelope<JsonObject>> {
    return this.http.request<ApiEnvelope<JsonObject>>({
      method: "POST",
      path: "/v1/suggestions/review-batch",
      json: { items: [...items], continue_on_error: input.continueOnError ?? false },
    });
  }
}

const suggestionPayload = (input: CreateSuggestionInput): JsonObject =>
  withoutUndefined({
    candidate_text: input.candidateText,
    safe_reason: input.safeReason,
    kind: input.kind ?? "note",
    source_refs: input.sourceRefs ?? [],
    trust_level: input.trustLevel ?? "medium",
    confidence: input.confidence ?? "medium",
    target_fact_id: input.targetFactId,
    target_fact_version: input.targetFactVersion,
    operation: input.operation ?? "add",
    category: input.category,
    tags: input.tags ?? [],
    ttl_policy: input.ttlPolicy,
    expires_at: input.expiresAt,
    expiry_reason: input.expiryReason,
    created_from_capture_id: input.createdFromCaptureId,
    candidate_fingerprint: input.candidateFingerprint,
    review_payload: input.reviewPayload,
    auto_approve: input.autoApprove,
  }) as JsonObject;

const validateTargetFactVersion = (input: CreateSuggestionInput, fieldName: string): void => {
  if (input.targetFactId && input.targetFactVersion === undefined) {
    throw new ValueError(`${fieldName} is required when targetFactId is set`);
  }
};
