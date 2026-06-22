import type { RequestExecutor } from "../client.js";
import { withoutUndefined } from "../payload.js";
import type { ApiEnvelope, MemoryScopeRecord, Space } from "../types.js";

export class SpacesClient {
  constructor(private readonly http: RequestExecutor) {}

  createSpace(input: { readonly slug: string; readonly name: string }): Promise<ApiEnvelope<Space>> {
    return this.http.request<ApiEnvelope<Space>>({
      method: "POST",
      path: "/v1/spaces",
      json: { slug: input.slug, name: input.name },
    });
  }

  listSpaces(input: { readonly limit?: number } = {}): Promise<ApiEnvelope<Space[]>> {
    return this.http.request<ApiEnvelope<Space[]>>({
      method: "GET",
      path: "/v1/spaces",
      params: withoutUndefined({ limit: input.limit }),
    });
  }

  createMemoryScope(input: {
    readonly spaceId: string;
    readonly externalRef: string;
    readonly name: string;
  }): Promise<ApiEnvelope<MemoryScopeRecord>> {
    return this.http.request<ApiEnvelope<MemoryScopeRecord>>({
      method: "POST",
      path: "/v1/memory-scopes",
      json: {
        space_id: input.spaceId,
        external_ref: input.externalRef,
        name: input.name,
      },
    });
  }

  listMemoryScopes(input: {
    readonly spaceId: string;
    readonly limit?: number;
  }): Promise<ApiEnvelope<MemoryScopeRecord[]>> {
    return this.http.request<ApiEnvelope<MemoryScopeRecord[]>>({
      method: "GET",
      path: "/v1/memory-scopes",
      params: withoutUndefined({ space_id: input.spaceId, limit: input.limit }),
    });
  }

  updateMemoryScope(
    memoryScopeId: string,
    input: { readonly externalRef?: string; readonly name?: string },
  ): Promise<ApiEnvelope<MemoryScopeRecord>> {
    return this.http.request<ApiEnvelope<MemoryScopeRecord>>({
      method: "PATCH",
      path: `/v1/memory-scopes/${memoryScopeId}`,
      json: withoutUndefined({ external_ref: input.externalRef, name: input.name }),
    });
  }

  deleteMemoryScope(memoryScopeId: string): Promise<ApiEnvelope<MemoryScopeRecord>> {
    return this.http.request<ApiEnvelope<MemoryScopeRecord>>({
      method: "DELETE",
      path: `/v1/memory-scopes/${memoryScopeId}`,
    });
  }
}
