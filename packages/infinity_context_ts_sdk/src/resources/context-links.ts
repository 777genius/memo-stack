import type { RequestExecutor } from "../client.js";
import { scopeQuery, withoutUndefined, ValueError, type SingleScopeInput } from "../payload.js";
import type {
  ApiEnvelope,
  ContextLinkRecord,
  ContextLinkSuggestionRecord,
  JsonObject,
} from "../types.js";

export interface ContextLinkCandidate extends JsonObject {
  readonly target_type: string;
  readonly target_id: string;
  readonly label?: string;
  readonly preview?: string;
  readonly score: number;
  readonly tier?: string;
  readonly reasons: readonly string[];
  readonly suggestion_id?: string | null;
  readonly status?: string | null;
  readonly metadata: JsonObject;
}

export interface SuggestContextLinksData extends JsonObject {
  readonly candidates: readonly ContextLinkCandidate[];
  readonly diagnostics: JsonObject;
}

export interface CreateContextLinkData extends ContextLinkRecord {
  readonly duplicate?: boolean;
}

export interface ReviewContextLinkSuggestionInput {
  readonly action: "approve" | "reject" | string;
  readonly reason?: string | undefined;
  readonly targetType?: string | undefined;
  readonly targetId?: string | undefined;
  readonly relationType?: string | undefined;
  readonly confidence?: string | undefined;
  readonly linkReason?: string | undefined;
}

export interface ReviewContextLinkSuggestionData extends JsonObject {
  readonly suggestion: ContextLinkSuggestionRecord;
  readonly link: ContextLinkRecord | null;
  readonly duplicate_link: boolean;
}

export interface ReviewContextLinkSuggestionBatchItemInput extends ReviewContextLinkSuggestionInput {
  readonly suggestionId: string;
}

export interface ReviewContextLinkSuggestionsBatchData extends JsonObject {
  readonly applied: number;
  readonly failed: number;
  readonly stopped: boolean;
  readonly diagnostics: JsonObject;
  readonly results: readonly JsonObject[];
}

export type ContextLinkVisibleFilterInput = SingleScopeInput & {
  readonly sourceType?: string | undefined;
  readonly sourceId?: string | undefined;
  readonly targetType?: string | undefined;
  readonly targetId?: string | undefined;
  readonly relationType?: string | undefined;
  readonly status?: string | null | undefined;
  readonly statuses?: string | undefined;
  readonly limit?: number | undefined;
};

export class ContextLinksClient {
  constructor(private readonly http: RequestExecutor) {}

  suggestContextLinks(input: SingleScopeInput & {
    readonly text?: string;
    readonly sourceType?: string;
    readonly sourceId?: string;
    readonly limit?: number;
    readonly persist?: boolean;
  }): Promise<ApiEnvelope<SuggestContextLinksData>> {
    return this.http.request<ApiEnvelope<SuggestContextLinksData>>({
      method: "POST",
      path: "/v1/link-suggestions",
      json: withoutUndefined({
        ...scopeQuery(input),
        text: input.text ?? "",
        source_type: input.sourceType,
        source_id: input.sourceId,
        limit: input.limit ?? 10,
        persist: input.persist ?? false,
      }) as JsonObject,
    });
  }

  createContextLink(input: SingleScopeInput & {
    readonly sourceType: string;
    readonly sourceId: string;
    readonly targetType: string;
    readonly targetId: string;
    readonly relationType?: string;
    readonly confidence?: string;
    readonly reason: string;
    readonly metadata?: JsonObject;
  }): Promise<ApiEnvelope<CreateContextLinkData>> {
    return this.http.request<ApiEnvelope<CreateContextLinkData>>({
      method: "POST",
      path: "/v1/context-links",
      json: withoutUndefined({
        ...scopeQuery(input),
        source_type: input.sourceType,
        source_id: input.sourceId,
        target_type: input.targetType,
        target_id: input.targetId,
        relation_type: input.relationType ?? "related_to",
        confidence: input.confidence ?? "medium",
        reason: input.reason,
        metadata: input.metadata,
      }) as JsonObject,
    });
  }

  listContextLinks(input: ContextLinkVisibleFilterInput): Promise<ApiEnvelope<ContextLinkRecord[]>> {
    return this.http.request<ApiEnvelope<ContextLinkRecord[]>>({
      method: "GET",
      path: "/v1/context-links",
      params: visibleFilterParams(input, "active"),
    });
  }

  updateContextLink(contextLinkId: string, input: {
    readonly sourceType?: string;
    readonly sourceId?: string;
    readonly targetType?: string;
    readonly targetId?: string;
    readonly relationType?: string;
    readonly confidence?: string;
    readonly reason?: string;
    readonly metadata?: JsonObject;
  }): Promise<ApiEnvelope<ContextLinkRecord>> {
    return this.http.request<ApiEnvelope<ContextLinkRecord>>({
      method: "PATCH",
      path: `/v1/context-links/${contextLinkId}`,
      json: withoutUndefined({
        source_type: input.sourceType,
        source_id: input.sourceId,
        target_type: input.targetType,
        target_id: input.targetId,
        relation_type: input.relationType,
        confidence: input.confidence,
        reason: input.reason,
        metadata: input.metadata,
      }) as JsonObject,
    });
  }

  deleteContextLink(contextLinkId: string): Promise<ApiEnvelope<ContextLinkRecord>> {
    return this.http.request<ApiEnvelope<ContextLinkRecord>>({
      method: "DELETE",
      path: `/v1/context-links/${contextLinkId}`,
    });
  }

  listContextLinkSuggestions(
    input: ContextLinkVisibleFilterInput,
  ): Promise<ApiEnvelope<ContextLinkSuggestionRecord[]>> {
    return this.http.request<ApiEnvelope<ContextLinkSuggestionRecord[]>>({
      method: "GET",
      path: "/v1/context-link-suggestions",
      params: visibleFilterParams(input, "pending"),
    });
  }

  reviewContextLinkSuggestion(
    suggestionId: string,
    input: ReviewContextLinkSuggestionInput,
  ): Promise<ApiEnvelope<ReviewContextLinkSuggestionData>> {
    return this.http.request<ApiEnvelope<ReviewContextLinkSuggestionData>>({
      method: "POST",
      path: `/v1/context-link-suggestions/${requiredText(
        suggestionId,
        "Context link review requires suggestionId",
      )}/review`,
      json: reviewPayload(input),
    });
  }

  approveContextLinkSuggestion(
    suggestionId: string,
    input: Omit<ReviewContextLinkSuggestionInput, "action"> = {},
  ): Promise<ApiEnvelope<ReviewContextLinkSuggestionData>> {
    return this.reviewContextLinkSuggestion(suggestionId, { ...input, action: "approve" });
  }

  rejectContextLinkSuggestion(
    suggestionId: string,
    input: { readonly reason?: string } = {},
  ): Promise<ApiEnvelope<ReviewContextLinkSuggestionData>> {
    return this.reviewContextLinkSuggestion(suggestionId, {
      action: "reject",
      ...(input.reason === undefined ? {} : { reason: input.reason }),
    });
  }

  reviewContextLinkSuggestionsBatch(
    items: readonly ReviewContextLinkSuggestionBatchItemInput[],
    input: {
      readonly continueOnError?: boolean;
      readonly visibleFilter?: ContextLinkVisibleFilterInput;
    } = {},
  ): Promise<ApiEnvelope<ReviewContextLinkSuggestionsBatchData>> {
    const normalizedItems = normalizeBatchItems(items);

    return this.http.request<ApiEnvelope<ReviewContextLinkSuggestionsBatchData>>({
      method: "POST",
      path: "/v1/context-link-suggestions/review-batch",
      json: withoutUndefined({
        items: normalizedItems,
        continue_on_error: input.continueOnError ?? false,
        visible_filter: input.visibleFilter === undefined ? undefined : visibleFilterParams(input.visibleFilter, "pending"),
      }) as JsonObject,
    });
  }
}

const visibleFilterParams = (input: ContextLinkVisibleFilterInput, defaultStatus: string): JsonObject =>
  withoutUndefined({
    ...scopeQuery(input),
    source_type: input.sourceType,
    source_id: input.sourceId,
    target_type: input.targetType,
    target_id: input.targetId,
    relation_type: input.relationType,
    status: input.statuses === undefined ? input.status ?? defaultStatus : undefined,
    statuses: input.statuses,
    limit: input.limit ?? 50,
  }) as JsonObject;

const reviewPayload = (input: ReviewContextLinkSuggestionInput): JsonObject =>
  withoutUndefined({
    action: requiredText(input.action, "Context link review requires action"),
    reason: input.reason,
    target_type: input.targetType,
    target_id: input.targetId,
    relation_type: input.relationType,
    confidence: input.confidence,
    link_reason: input.linkReason,
  }) as JsonObject;

const normalizeBatchItems = (items: readonly ReviewContextLinkSuggestionBatchItemInput[]): readonly JsonObject[] => {
  if (items.length === 0) {
    throw new ValueError("Context link batch review requires at least one item");
  }
  if (items.length > 50) {
    throw new ValueError("Context link batch review supports at most 50 items");
  }

  const seen = new Set<string>();

  return items.map((item) => {
    const suggestionId = requiredText(item.suggestionId, "Context link batch review requires suggestionId");
    if (seen.has(suggestionId)) {
      throw new ValueError("Context link batch review requires unique suggestionId values");
    }
    seen.add(suggestionId);

    return {
      suggestion_id: suggestionId,
      ...reviewPayload(item),
    };
  });
};

const requiredText = (value: string, message: string): string => {
  const text = value.trim();
  if (text.length === 0) {
    throw new ValueError(message);
  }

  return text;
};
