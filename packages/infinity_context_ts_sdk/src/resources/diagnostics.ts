import { requestControls, type RequestControls, type RequestExecutor } from "../client.js";
import { withoutUndefined } from "../payload.js";
import type { ApiEnvelope, JsonObject } from "../types.js";

export class DiagnosticsClient {
  constructor(private readonly http: RequestExecutor) {}

  adapters(input: RequestControls = {}): Promise<JsonObject> {
    return this.http.request<JsonObject>({
      method: "GET",
      path: "/v1/diagnostics/adapters",
      ...requestControls(input),
    });
  }

  outbox(input: { readonly limit?: number; readonly cursor?: string } & RequestControls = {}): Promise<JsonObject> {
    return this.http.request<JsonObject>({
      method: "GET",
      path: "/v1/diagnostics/outbox",
      ...requestControls(input),
      params: withoutUndefined({ limit: input.limit ?? 100, cursor: input.cursor }),
    });
  }

  memoryScope(memoryScopeId: string, input: RequestControls = {}): Promise<JsonObject> {
    return this.http.request<JsonObject>({
      method: "GET",
      path: `/v1/diagnostics/memory-scope/${memoryScopeId}`,
      ...requestControls(input),
    });
  }

  metrics(input: RequestControls = {}): Promise<JsonObject> {
    return this.http.request<JsonObject>({
      method: "GET",
      path: "/v1/diagnostics/metrics",
      ...requestControls(input),
    });
  }

  storage(input: RequestControls = {}): Promise<JsonObject> {
    return this.http.request<JsonObject>({
      method: "GET",
      path: "/v1/diagnostics/storage",
      ...requestControls(input),
    });
  }

  operationsConsole(input: { readonly limit?: number } & RequestControls = {}): Promise<ApiEnvelope<JsonObject>> {
    return this.http.request<ApiEnvelope<JsonObject>>({
      method: "GET",
      path: "/v1/operations-console",
      ...requestControls(input),
      params: { limit: input.limit ?? 50 },
    });
  }
}
