import type { RequestExecutor } from "../client.js";
import type { InfinityContextCapabilities, InfinityContextHealth } from "../types.js";

export class SystemClient {
  constructor(private readonly http: RequestExecutor) {}

  health(): Promise<InfinityContextHealth> {
    return this.http.request<InfinityContextHealth>({ method: "GET", path: "/v1/health" });
  }

  capabilities(): Promise<InfinityContextCapabilities> {
    return this.http.request<InfinityContextCapabilities>({
      method: "GET",
      path: "/v1/capabilities",
    });
  }
}
