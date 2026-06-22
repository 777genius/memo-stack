import type { RequestExecutor } from "../client.js";
import { scopeQuery, withoutUndefined, type SingleScopeInput } from "../payload.js";
import type { AnchorRecord, ApiEnvelope, JsonObject, SourceRef } from "../types.js";

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
}
