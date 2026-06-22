import { requestControls, type RequestControls, type RequestExecutor } from "../client.js";
import {
  collectCursorItems,
  iterateCursorItems,
  type CursorPaginationOptions,
} from "../pagination.js";
import { withoutUndefined } from "../payload.js";
import type { ApiEnvelope, JsonObject } from "../types.js";

export interface ListOutboxDiagnosticsInput extends RequestControls {
  readonly limit?: number;
  readonly cursor?: string;
}

export interface OutboxDiagnosticItem extends JsonObject {
  readonly id: number;
  readonly event_type: string;
  readonly aggregate_type: string;
  readonly aggregate_id: string;
  readonly aggregate_version: number;
  readonly workload_class: string;
  readonly fairness_key: string;
  readonly status: string;
  readonly attempt_count: number;
  readonly last_safe_error: string | null;
  readonly last_safe_diagnostic_code: string | null;
  readonly next_attempt_at: string;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface OutboxDiagnosticsData extends JsonObject {
  readonly counts: JsonObject;
  readonly oldest_active_lag_seconds?: number | null;
  readonly items: readonly OutboxDiagnosticItem[];
  readonly next_cursor?: string | null;
}

export type OutboxDiagnosticsResponse = ApiEnvelope<OutboxDiagnosticsData> & JsonObject;

export class DiagnosticsClient {
  constructor(private readonly http: RequestExecutor) {}

  adapters(input: RequestControls = {}): Promise<JsonObject> {
    return this.http.request<JsonObject>({
      method: "GET",
      path: "/v1/diagnostics/adapters",
      ...requestControls(input),
    });
  }

  outbox(input: ListOutboxDiagnosticsInput = {}): Promise<OutboxDiagnosticsResponse> {
    return this.http.request<OutboxDiagnosticsResponse>({
      method: "GET",
      path: "/v1/diagnostics/outbox",
      ...requestControls(input),
      params: withoutUndefined({ limit: input.limit ?? 100, cursor: input.cursor }),
    });
  }

  iterateOutboxItems(options: CursorPaginationOptions = {}): AsyncIterable<OutboxDiagnosticItem> {
    return iterateCursorItems<OutboxDiagnosticItem>(
      async (page) => {
        const response = await this.outbox(page);
        return {
          data: response.data.items,
          next_cursor: response.data.next_cursor ?? null,
        };
      },
      options,
    );
  }

  listAllOutboxItems(options: CursorPaginationOptions = {}): Promise<readonly OutboxDiagnosticItem[]> {
    return collectCursorItems<OutboxDiagnosticItem>(
      async (page) => {
        const response = await this.outbox(page);
        return {
          data: response.data.items,
          next_cursor: response.data.next_cursor ?? null,
        };
      },
      options,
    );
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
