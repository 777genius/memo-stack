import type { RequestExecutor } from "../client.js";
import { withoutUndefined } from "../payload.js";
import type { ApiEnvelope, UsageSummaryData } from "../types.js";

export type UsageSummaryInput = {
  readonly spaceId?: string;
  readonly spaceSlug?: string;
};

export class UsageClient {
  constructor(private readonly http: RequestExecutor) {}

  summary(input: UsageSummaryInput = {}): Promise<ApiEnvelope<UsageSummaryData>> {
    return this.http.request<ApiEnvelope<UsageSummaryData>>({
      method: "GET",
      path: "/v1/usage",
      params: withoutUndefined({
        space_id: input.spaceId,
        space_slug: input.spaceSlug,
      }),
    });
  }
}
