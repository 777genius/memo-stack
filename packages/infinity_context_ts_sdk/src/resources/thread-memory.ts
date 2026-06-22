import { requestControls, type RequestControls, type RequestExecutor } from "../client.js";
import { singleScopePayload, type SingleScopeInput } from "../payload.js";
import type { ApiEnvelope, DeleteThreadMemoryData, ThreadMemoryStatusData } from "../types.js";

export class ThreadMemoryClient {
  constructor(private readonly http: RequestExecutor) {}

  status(input: SingleScopeInput & RequestControls): Promise<ApiEnvelope<ThreadMemoryStatusData>> {
    return this.http.request<ApiEnvelope<ThreadMemoryStatusData>>({
      method: "POST",
      path: "/v1/thread-memory/status",
      ...requestControls(input),
      json: singleScopePayload(input),
    });
  }

  delete(input: SingleScopeInput & RequestControls): Promise<ApiEnvelope<DeleteThreadMemoryData>> {
    return this.http.request<ApiEnvelope<DeleteThreadMemoryData>>({
      method: "DELETE",
      path: "/v1/thread-memory",
      ...requestControls(input),
      json: singleScopePayload(input),
    });
  }

  deleteCompat(input: SingleScopeInput & RequestControls): Promise<ApiEnvelope<DeleteThreadMemoryData>> {
    return this.http.request<ApiEnvelope<DeleteThreadMemoryData>>({
      method: "POST",
      path: "/v1/thread-memory/delete",
      ...requestControls(input),
      json: singleScopePayload(input),
    });
  }
}
