import type { RequestExecutor } from "../client.js";
import { scopeQuery, withoutUndefined, type SingleScopeInput } from "../payload.js";
import type { ApiEnvelope, AssetRecord, JsonObject } from "../types.js";

export class AssetsClient {
  constructor(private readonly http: RequestExecutor) {}

  uploadAsset(input: SingleScopeInput & {
    readonly filename: string;
    readonly content: BodyInit;
    readonly contentType?: string;
    readonly classification?: string;
    readonly extract?: boolean;
    readonly parserProfile?: string;
  }): Promise<ApiEnvelope<AssetRecord>> {
    return this.http.request<ApiEnvelope<AssetRecord>>({
      method: "POST",
      path: "/v1/assets",
      params: withoutUndefined({
        ...scopeQuery(input),
        filename: input.filename,
        content_type: input.contentType,
        classification: input.classification ?? "unknown",
        extract: input.extract ?? false,
        parser_profile: input.parserProfile,
      }),
      bytes: input.content,
      contentType: input.contentType,
    });
  }

  listAssets(input: SingleScopeInput & {
    readonly status?: string | null;
    readonly limit?: number;
  }): Promise<ApiEnvelope<AssetRecord[]>> {
    return this.http.request<ApiEnvelope<AssetRecord[]>>({
      method: "GET",
      path: "/v1/assets",
      params: withoutUndefined({
        ...scopeQuery(input),
        status: input.status === undefined ? "stored" : input.status,
        limit: input.limit ?? 50,
      }),
    });
  }

  getAsset(assetId: string): Promise<ApiEnvelope<AssetRecord>> {
    return this.http.request<ApiEnvelope<AssetRecord>>({
      method: "GET",
      path: `/v1/assets/${assetId}`,
    });
  }

  deleteAsset(assetId: string): Promise<ApiEnvelope<AssetRecord>> {
    return this.http.request<ApiEnvelope<AssetRecord>>({
      method: "DELETE",
      path: `/v1/assets/${assetId}`,
    });
  }

  downloadAsset(assetId: string): Promise<Uint8Array> {
    return this.http.request<Uint8Array>({
      method: "GET",
      path: `/v1/assets/${assetId}/download`,
      responseType: "bytes",
    });
  }

  requestAssetExtraction(assetId: string, input: { readonly parserProfile?: string } = {}): Promise<ApiEnvelope<JsonObject>> {
    return this.http.request<ApiEnvelope<JsonObject>>({
      method: "POST",
      path: `/v1/assets/${assetId}/extractions`,
      params: withoutUndefined({ parser_profile: input.parserProfile }),
    });
  }

  getAssetExtraction(jobId: string): Promise<ApiEnvelope<JsonObject>> {
    return this.http.request<ApiEnvelope<JsonObject>>({
      method: "GET",
      path: `/v1/asset-extractions/${jobId}`,
    });
  }

  downloadExtractionArtifact(artifactId: string): Promise<Uint8Array> {
    return this.http.request<Uint8Array>({
      method: "GET",
      path: `/v1/extraction-artifacts/${artifactId}/download`,
      responseType: "bytes",
    });
  }
}
