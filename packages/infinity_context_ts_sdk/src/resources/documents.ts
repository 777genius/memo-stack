import type { RequestExecutor } from "../client.js";
import {
  collectCursorItems,
  iterateCursorItems,
  type CursorPaginationOptions,
  type PaginatedEnvelope,
} from "../pagination.js";
import { scopeQuery, singleScopePayload, withoutUndefined, type SingleScopeInput } from "../payload.js";
import type { ApiEnvelope, DocumentRecord, JsonObject, SourceRef } from "../types.js";

export interface ListDocumentChunksInput {
  readonly limit?: number;
  readonly cursor?: string;
}

export class DocumentsClient {
  constructor(private readonly http: RequestExecutor) {}

  ingestDocument(input: SingleScopeInput & {
    readonly title: string;
    readonly text: string;
    readonly sourceExternalId: string;
    readonly sourceType?: string;
    readonly classification?: string;
    readonly sourceRefs?: readonly SourceRef[];
    readonly idempotencyKey?: string;
  }): Promise<ApiEnvelope<DocumentRecord>> {
    return this.http.request<ApiEnvelope<DocumentRecord>>({
      method: "POST",
      path: "/v1/documents",
      idempotencyKey: input.idempotencyKey,
      json: withoutUndefined({
        ...singleScopePayload(input),
        title: input.title,
        text: input.text,
        source_type: input.sourceType ?? "document",
        source_external_id: input.sourceExternalId,
        classification: input.classification ?? "unknown",
        source_refs: input.sourceRefs,
      }) as JsonObject,
    });
  }

  ingestEpisode(input: SingleScopeInput & {
    readonly sourceExternalId: string;
    readonly text: string;
    readonly sourceType?: string;
    readonly occurredAt?: string;
    readonly speaker?: string;
    readonly trustLevel?: string;
    readonly kindHint?: string;
    readonly language?: string;
    readonly metadata?: JsonObject;
    readonly idempotencyKey?: string;
  }): Promise<ApiEnvelope<JsonObject>> {
    return this.http.request<ApiEnvelope<JsonObject>>({
      method: "POST",
      path: "/v1/episodes",
      idempotencyKey: input.idempotencyKey,
      json: withoutUndefined({
        ...singleScopePayload(input),
        source_type: input.sourceType ?? "unknown",
        source_external_id: input.sourceExternalId,
        text: input.text,
        occurred_at: input.occurredAt,
        speaker: input.speaker,
        trust_level: input.trustLevel ?? "medium",
        kind_hint: input.kindHint,
        language: input.language,
        metadata: input.metadata,
      }) as JsonObject,
    });
  }

  getDocument(documentId: string): Promise<ApiEnvelope<DocumentRecord>> {
    return this.http.request<ApiEnvelope<DocumentRecord>>({
      method: "GET",
      path: `/v1/documents/${documentId}`,
    });
  }

  listDocumentChunks(
    documentId: string,
    input: ListDocumentChunksInput = {},
  ): Promise<PaginatedEnvelope<JsonObject[]>> {
    return this.http.request<PaginatedEnvelope<JsonObject[]>>({
      method: "GET",
      path: `/v1/documents/${documentId}/chunks`,
      params: withoutUndefined({ limit: input.limit ?? 100, cursor: input.cursor }),
    });
  }

  iterateDocumentChunks(
    documentId: string,
    options: CursorPaginationOptions = {},
  ): AsyncIterable<JsonObject> {
    return iterateCursorItems<JsonObject>(
      (page) => this.listDocumentChunks(documentId, page),
      options,
    );
  }

  listAllDocumentChunks(
    documentId: string,
    options: CursorPaginationOptions = {},
  ): Promise<readonly JsonObject[]> {
    return collectCursorItems<JsonObject>(
      (page) => this.listDocumentChunks(documentId, page),
      options,
    );
  }

  processDocument(
    documentId: string,
    input: { readonly idempotencyKey?: string } = {},
  ): Promise<ApiEnvelope<DocumentRecord>> {
    return this.http.request<ApiEnvelope<DocumentRecord>>({
      method: "POST",
      path: `/v1/documents/${documentId}/process`,
      idempotencyKey: input.idempotencyKey,
    });
  }

  deleteDocument(documentId: string): Promise<ApiEnvelope<DocumentRecord>> {
    return this.http.request<ApiEnvelope<DocumentRecord>>({
      method: "DELETE",
      path: `/v1/documents/${documentId}`,
    });
  }

  listScopeDocuments(input: SingleScopeInput & { readonly limit?: number }): Promise<ApiEnvelope<DocumentRecord[]>> {
    return this.http.request<ApiEnvelope<DocumentRecord[]>>({
      method: "GET",
      path: "/v1/documents",
      params: withoutUndefined({ ...scopeQuery(input), limit: input.limit ?? 100 }),
    });
  }
}
