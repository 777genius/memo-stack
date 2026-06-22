import { requestControls, type RequestControls, type RequestExecutor } from "../client.js";
import { withoutUndefined } from "../payload.js";
import type { ApiEnvelope, JsonObject, SpaceMembership, UserRecord } from "../types.js";

export class UsersClient {
  constructor(private readonly http: RequestExecutor) {}

  createUser(input: {
    readonly externalRef: string;
    readonly displayName: string;
    readonly email?: string;
    readonly metadata?: JsonObject;
  } & RequestControls): Promise<ApiEnvelope<UserRecord>> {
    return this.http.request<ApiEnvelope<UserRecord>>({
      method: "POST",
      path: "/v1/users",
      ...requestControls(input),
      json: withoutUndefined({
        external_ref: input.externalRef,
        display_name: input.displayName,
        email: input.email,
        metadata: input.metadata,
      }) as JsonObject,
    });
  }

  listUsers(
    input: { readonly status?: string | null; readonly limit?: number } & RequestControls = {},
  ): Promise<ApiEnvelope<UserRecord[]>> {
    return this.http.request<ApiEnvelope<UserRecord[]>>({
      method: "GET",
      path: "/v1/users",
      ...requestControls(input),
      params: withoutUndefined({
        status: input.status === undefined ? "active" : input.status,
        limit: input.limit ?? 100,
      }),
    });
  }

  createSpaceMembership(spaceId: string, input: {
    readonly userId: string;
    readonly role?: string;
  } & RequestControls): Promise<ApiEnvelope<SpaceMembership>> {
    return this.http.request<ApiEnvelope<SpaceMembership>>({
      method: "POST",
      path: `/v1/spaces/${spaceId}/memberships`,
      ...requestControls(input),
      json: {
        user_id: input.userId,
        role: input.role ?? "member",
      },
    });
  }

  listSpaceMemberships(
    spaceId: string,
    input: { readonly status?: string | null; readonly limit?: number } & RequestControls = {},
  ): Promise<ApiEnvelope<SpaceMembership[]>> {
    return this.http.request<ApiEnvelope<SpaceMembership[]>>({
      method: "GET",
      path: `/v1/spaces/${spaceId}/memberships`,
      ...requestControls(input),
      params: withoutUndefined({
        status: input.status === undefined ? "active" : input.status,
        limit: input.limit ?? 100,
      }),
    });
  }

  checkSpaceAccess(
    spaceId: string,
    userId: string,
    input: { readonly requiredRole?: string } & RequestControls = {},
  ): Promise<ApiEnvelope<JsonObject>> {
    return this.http.request<ApiEnvelope<JsonObject>>({
      method: "GET",
      path: `/v1/spaces/${spaceId}/memberships/${userId}/access`,
      ...requestControls(input),
      params: { required_role: input.requiredRole ?? "viewer" },
    });
  }
}
