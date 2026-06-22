import type { RequestExecutor } from "../client.js";
import { scopeQuery, withoutUndefined, type SingleScopeInput } from "../payload.js";
import type { AnchorRecord, ApiEnvelope, JsonObject, SourceRef } from "../types.js";

type AnchorScopeInput = Omit<SingleScopeInput, "threadId" | "threadExternalRef">;

export interface AnchorBackfillSource extends JsonObject {
  readonly source_type: string;
  readonly scanned: number;
  readonly observed: number;
  readonly skipped_conflicts: number;
}

export interface AnchorBackfillData extends JsonObject {
  readonly anchors: readonly AnchorRecord[];
  readonly created: number;
  readonly updated: number;
  readonly sources: readonly AnchorBackfillSource[];
  readonly diagnostics: JsonObject;
}

export interface AnchorMergeCandidate extends JsonObject {
  readonly source_anchor: AnchorRecord;
  readonly target_anchor: AnchorRecord;
  readonly confidence: string;
  readonly score: number;
  readonly reasons: readonly string[];
  readonly metadata: JsonObject;
}

export class AnchorsClient {
  constructor(private readonly http: RequestExecutor) {}

  createAnchor(input: SingleScopeInput & {
    readonly kind: string;
    readonly label: string;
    readonly aliases?: readonly string[];
    readonly description?: string;
    readonly confidence?: string;
    readonly evidenceRefs?: readonly SourceRef[];
    readonly observedAt?: string;
    readonly validFrom?: string;
    readonly validTo?: string;
    readonly metadata?: JsonObject;
  }): Promise<ApiEnvelope<AnchorRecord>> {
    return this.http.request<ApiEnvelope<AnchorRecord>>({
      method: "POST",
      path: "/v1/anchors",
      json: withoutUndefined({
        ...scopeQuery(input),
        kind: input.kind,
        label: input.label,
        aliases: input.aliases ?? [],
        description: input.description,
        confidence: input.confidence,
        evidence_refs: input.evidenceRefs,
        observed_at: input.observedAt,
        valid_from: input.validFrom,
        valid_to: input.validTo,
        metadata: input.metadata ?? {},
      }) as JsonObject,
    });
  }

  listAnchors(input: SingleScopeInput & {
    readonly kind?: string;
    readonly status?: string | null;
    readonly limit?: number;
  }): Promise<ApiEnvelope<AnchorRecord[]>> {
    return this.http.request<ApiEnvelope<AnchorRecord[]>>({
      method: "GET",
      path: "/v1/anchors",
      params: withoutUndefined({
        ...scopeQuery(input),
        kind: input.kind,
        status: input.status === undefined ? "active" : input.status,
        limit: input.limit ?? 100,
      }),
    });
  }

  listAnchorRelations(input: SingleScopeInput & {
    readonly status?: string | null;
    readonly limit?: number;
    readonly anchorLimit?: number;
  }): Promise<ApiEnvelope<JsonObject[]>> {
    return this.http.request<ApiEnvelope<JsonObject[]>>({
      method: "GET",
      path: "/v1/anchors/relations",
      params: withoutUndefined({
        ...scopeQuery(input),
        status: input.status === undefined ? "active" : input.status,
        limit: input.limit ?? 100,
        anchor_limit: input.anchorLimit ?? 500,
      }),
    });
  }

  updateAnchor(anchorId: string, input: {
    readonly label?: string;
    readonly aliases?: readonly string[];
    readonly description?: string;
    readonly confidence?: string;
    readonly evidenceRefs?: readonly SourceRef[];
    readonly observedAt?: string;
    readonly validFrom?: string;
    readonly validTo?: string;
    readonly metadata?: JsonObject;
  }): Promise<ApiEnvelope<AnchorRecord>> {
    return this.http.request<ApiEnvelope<AnchorRecord>>({
      method: "PATCH",
      path: `/v1/anchors/${anchorId}`,
      json: withoutUndefined({
        label: input.label,
        aliases: input.aliases,
        description: input.description,
        confidence: input.confidence,
        evidence_refs: input.evidenceRefs,
        observed_at: input.observedAt,
        valid_from: input.validFrom,
        valid_to: input.validTo,
        metadata: input.metadata,
      }) as JsonObject,
    });
  }

  deleteAnchor(anchorId: string, input: { readonly reason?: string } = {}): Promise<ApiEnvelope<AnchorRecord>> {
    return this.http.request<ApiEnvelope<AnchorRecord>>({
      method: "DELETE",
      path: `/v1/anchors/${anchorId}`,
      json: { reason: input.reason ?? "manual delete" },
    });
  }

  backfillAnchors(input: AnchorScopeInput & {
    readonly limitPerSource?: number;
  }): Promise<ApiEnvelope<AnchorBackfillData>> {
    return this.http.request<ApiEnvelope<AnchorBackfillData>>({
      method: "POST",
      path: "/v1/anchors/backfill",
      json: withoutUndefined({
        ...scopeQuery(input),
        limit_per_source: input.limitPerSource ?? 100,
      }) as JsonObject,
    });
  }

  listAnchorMergeSuggestions(input: AnchorScopeInput & {
    readonly kind?: string;
    readonly limit?: number;
  }): Promise<ApiEnvelope<AnchorMergeCandidate[]>> {
    return this.http.request<ApiEnvelope<AnchorMergeCandidate[]>>({
      method: "GET",
      path: "/v1/anchors/merge-suggestions",
      params: withoutUndefined({
        ...scopeQuery(input),
        kind: input.kind,
        limit: input.limit ?? 50,
      }),
    });
  }

  mergeAnchor(
    sourceAnchorId: string,
    input: { readonly targetAnchorId: string; readonly reason: string },
  ): Promise<ApiEnvelope<AnchorRecord>> {
    return this.http.request<ApiEnvelope<AnchorRecord>>({
      method: "POST",
      path: `/v1/anchors/${sourceAnchorId}/merge`,
      json: {
        target_anchor_id: input.targetAnchorId,
        reason: input.reason,
      },
    });
  }

  splitAnchor(
    anchorId: string,
    input: { readonly alias: string; readonly newLabel?: string; readonly reason?: string },
  ): Promise<ApiEnvelope<AnchorRecord>> {
    return this.http.request<ApiEnvelope<AnchorRecord>>({
      method: "POST",
      path: `/v1/anchors/${anchorId}/split`,
      json: withoutUndefined({
        alias: input.alias,
        new_label: input.newLabel,
        reason: input.reason ?? "manual split",
      }) as JsonObject,
    });
  }
}
