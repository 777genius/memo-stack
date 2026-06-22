import type { RequestExecutor } from "../client.js";
import { withoutUndefined } from "../payload.js";
import type { ApiEnvelope, JsonObject } from "../types.js";

export class DiagnosticsClient {
  constructor(private readonly http: RequestExecutor) {}

  adapters(): Promise<JsonObject> {
    return this.http.request<JsonObject>({ method: "GET", path: "/v1/diagnostics/adapters" });
  }

  outbox(input: { readonly limit?: number; readonly cursor?: string } = {}): Promise<JsonObject> {
    return this.http.request<JsonObject>({
      method: "GET",
      path: "/v1/diagnostics/outbox",
      params: withoutUndefined({ limit: input.limit ?? 100, cursor: input.cursor }),
    });
  }

  memoryScope(memoryScopeId: string): Promise<JsonObject> {
    return this.http.request<JsonObject>({
      method: "GET",
      path: `/v1/diagnostics/memory-scope/${memoryScopeId}`,
    });
  }

  metrics(): Promise<JsonObject> {
    return this.http.request<JsonObject>({ method: "GET", path: "/v1/diagnostics/metrics" });
  }

  storage(): Promise<JsonObject> {
    return this.http.request<JsonObject>({ method: "GET", path: "/v1/diagnostics/storage" });
  }

  operationsConsole(input: { readonly limit?: number } = {}): Promise<ApiEnvelope<JsonObject>> {
    return this.http.request<ApiEnvelope<JsonObject>>({
      method: "GET",
      path: "/v1/operations-console",
      params: { limit: input.limit ?? 50 },
    });
  }
}
