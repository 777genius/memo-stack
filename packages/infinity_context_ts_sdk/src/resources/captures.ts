import type { RequestExecutor } from "../client.js";
import { scopeQuery, withoutUndefined, type SingleScopeInput } from "../payload.js";
import type { ApiEnvelope, CaptureRecord, JsonObject, SourceRef } from "../types.js";

export interface CreateCaptureData extends CaptureRecord {
  readonly duplicate: boolean;
  readonly created_suggestions: number;
  readonly suggestion_ids: readonly string[];
  readonly auto_applied_facts: number;
  readonly auto_applied_fact_ids: readonly string[];
}

export interface ConsolidateCaptureData extends CaptureRecord {
  readonly created_suggestions: number;
  readonly suggestion_ids: readonly string[];
  readonly auto_applied_facts: number;
  readonly auto_applied_fact_ids: readonly string[];
}

export class CapturesClient {
  constructor(private readonly http: RequestExecutor) {}

  createCapture(input: SingleScopeInput & {
    readonly sourceAgent: string;
    readonly eventType: string;
    readonly text: string;
    readonly sourceKind?: string;
    readonly actorRole?: string;
    readonly sourceEventId?: string;
    readonly sourceActorExternalRef?: string;
    readonly clientInstanceId?: string;
    readonly agentSessionExternalRef?: string;
    readonly turnExternalRef?: string;
    readonly parentCaptureId?: string;
    readonly sequenceIndex?: number;
    readonly evidenceRefs?: readonly SourceRef[];
    readonly trustLevel?: string;
    readonly sourceAuthority?: string;
    readonly sensitivity?: string;
    readonly dataClassification?: string;
    readonly occurredAt?: string;
    readonly metadata?: JsonObject;
    readonly traceId?: string;
    readonly idempotencyKey?: string;
    readonly consolidate?: boolean;
  }): Promise<ApiEnvelope<CreateCaptureData>> {
    return this.http.request<ApiEnvelope<CreateCaptureData>>({
      method: "POST",
      path: "/v1/captures",
      json: withoutUndefined({
        ...scopeQuery(input),
        source_agent: input.sourceAgent,
        source_kind: input.sourceKind ?? "hook",
        event_type: input.eventType,
        actor_role: input.actorRole ?? "unknown",
        text: input.text,
        source_event_id: input.sourceEventId,
        source_actor_external_ref: input.sourceActorExternalRef,
        client_instance_id: input.clientInstanceId,
        agent_session_external_ref: input.agentSessionExternalRef,
        turn_external_ref: input.turnExternalRef,
        parent_capture_id: input.parentCaptureId,
        sequence_index: input.sequenceIndex,
        evidence_refs: input.evidenceRefs ?? [],
        trust_level: input.trustLevel ?? "medium",
        source_authority: input.sourceAuthority ?? "unknown",
        sensitivity: input.sensitivity ?? "medium",
        data_classification: input.dataClassification ?? "internal",
        occurred_at: input.occurredAt,
        metadata: input.metadata,
        trace_id: input.traceId,
        idempotency_key: input.idempotencyKey,
        consolidate: input.consolidate,
      }) as JsonObject,
    });
  }

  listCaptures(input: SingleScopeInput & {
    readonly status?: string | null;
    readonly consolidationStatus?: string | null;
    readonly limit?: number;
  }): Promise<ApiEnvelope<CaptureRecord[]>> {
    return this.http.request<ApiEnvelope<CaptureRecord[]>>({
      method: "GET",
      path: "/v1/captures",
      params: captureQuery(input),
    });
  }

  getCapture(captureId: string): Promise<ApiEnvelope<CaptureRecord | null>> {
    return this.http.request<ApiEnvelope<CaptureRecord | null>>({
      method: "GET",
      path: `/v1/captures/${captureId}`,
    });
  }

  consolidateCapture(
    captureId: string,
    input: { readonly force?: boolean } = {},
  ): Promise<ApiEnvelope<ConsolidateCaptureData>> {
    return this.http.request<ApiEnvelope<ConsolidateCaptureData>>({
      method: "POST",
      path: `/v1/captures/${captureId}/consolidate`,
      json: { force: input.force ?? false },
    });
  }

  purgeCapture(
    captureId: string,
    input: { readonly reason?: string } = {},
  ): Promise<ApiEnvelope<CaptureRecord>> {
    return this.http.request<ApiEnvelope<CaptureRecord>>({
      method: "DELETE",
      path: `/v1/captures/${captureId}`,
      json: { reason: input.reason ?? "privacy_purge" },
    });
  }

  captureDiagnostics(input: SingleScopeInput & {
    readonly consolidationStatus?: string | null;
    readonly limit?: number;
  }): Promise<ApiEnvelope<CaptureRecord[]>> {
    return this.http.request<ApiEnvelope<CaptureRecord[]>>({
      method: "GET",
      path: "/v1/diagnostics/captures",
      params: captureQuery(input),
    });
  }
}

const captureQuery = (
  input: SingleScopeInput & {
    readonly status?: string | null;
    readonly consolidationStatus?: string | null;
    readonly limit?: number;
  },
): JsonObject =>
  withoutUndefined({
    ...scopeQuery(input),
    status: input.status,
    consolidation_status: input.consolidationStatus,
    limit: input.limit ?? 50,
  }) as JsonObject;
