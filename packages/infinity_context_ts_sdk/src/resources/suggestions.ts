import type { RequestExecutor } from "../client.js";
import { scopeQuery, withoutUndefined, type SingleScopeInput } from "../payload.js";
import type { ApiEnvelope, JsonObject, SourceRef, SuggestionRecord } from "../types.js";

export class SuggestionsClient {
  constructor(private readonly http: RequestExecutor) {}

  createSuggestion(input: SingleScopeInput & {
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
    readonly candidateFingerprint?: string;
    readonly reviewPayload?: JsonObject;
  }): Promise<ApiEnvelope<SuggestionRecord>> {
    return this.http.request<ApiEnvelope<SuggestionRecord>>({
      method: "POST",
      path: "/v1/suggestions",
      json: withoutUndefined({
        ...scopeQuery(input),
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
        candidate_fingerprint: input.candidateFingerprint,
        review_payload: input.reviewPayload,
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
