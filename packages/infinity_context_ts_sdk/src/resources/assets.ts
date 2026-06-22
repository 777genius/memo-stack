import { requestControls, type RequestControls, type RequestExecutor } from "../client.js";
import { scopeQuery, withoutUndefined, type SingleScopeInput } from "../payload.js";
import type {
  ApiEnvelope,
  AssetExtractionDetails,
  AssetExtractionJobRecord,
  AssetRecord,
  JsonObject,
} from "../types.js";

export type AssetExtractionListInput = RequestControls & {
  readonly status?: string | null;
  readonly limit?: number;
};

export class AssetsClient {
  constructor(private readonly http: RequestExecutor) {}

  uploadAsset(input: SingleScopeInput & RequestControls & {
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
      ...requestControls(input),
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

  listAssets(input: SingleScopeInput & RequestControls & {
    readonly status?: string | null;
    readonly limit?: number;
  }): Promise<ApiEnvelope<AssetRecord[]>> {
    return this.http.request<ApiEnvelope<AssetRecord[]>>({
      method: "GET",
      path: "/v1/assets",
      ...requestControls(input),
      params: withoutUndefined({
        ...scopeQuery(input),
        status: input.status === undefined ? "stored" : input.status,
        limit: input.limit ?? 50,
      }),
    });
  }

  getAsset(assetId: string, input: RequestControls = {}): Promise<ApiEnvelope<AssetRecord>> {
    return this.http.request<ApiEnvelope<AssetRecord>>({
      method: "GET",
      path: `/v1/assets/${assetId}`,
      ...requestControls(input),
    });
  }

  deleteAsset(assetId: string, input: RequestControls = {}): Promise<ApiEnvelope<AssetRecord>> {
    return this.http.request<ApiEnvelope<AssetRecord>>({
      method: "DELETE",
      path: `/v1/assets/${assetId}`,
      ...requestControls(input),
    });
  }

  downloadAsset(assetId: string, input: RequestControls = {}): Promise<Uint8Array> {
    return this.http.request<Uint8Array>({
      method: "GET",
      path: `/v1/assets/${assetId}/download`,
      ...requestControls(input),
      responseType: "bytes",
    });
  }

  requestAssetExtraction(
    assetId: string,
    input: { readonly parserProfile?: string } & RequestControls = {},
  ): Promise<ApiEnvelope<AssetExtractionJobRecord>> {
    return this.http.request<ApiEnvelope<AssetExtractionJobRecord>>({
      method: "POST",
      path: `/v1/assets/${assetId}/extractions`,
      ...requestControls(input),
      params: withoutUndefined({ parser_profile: input.parserProfile }),
    });
  }

  listAssetExtractions(
    assetId: string,
    input: AssetExtractionListInput = {},
  ): Promise<ApiEnvelope<AssetExtractionJobRecord[]>> {
    return this.http.request<ApiEnvelope<AssetExtractionJobRecord[]>>({
      method: "GET",
      path: `/v1/assets/${assetId}/extractions`,
      ...requestControls(input),
      params: extractionListQuery(input),
    });
  }

  listScopeAssetExtractions(
    input: SingleScopeInput & AssetExtractionListInput,
  ): Promise<ApiEnvelope<AssetExtractionJobRecord[]>> {
    return this.http.request<ApiEnvelope<AssetExtractionJobRecord[]>>({
      method: "GET",
      path: "/v1/asset-extractions",
      ...requestControls(input),
      params: withoutUndefined({
        ...scopeQuery(input),
        status: input.status,
        limit: input.limit ?? 50,
      }),
    });
  }

  getAssetExtraction(jobId: string, input: RequestControls = {}): Promise<ApiEnvelope<AssetExtractionDetails>> {
    return this.http.request<ApiEnvelope<AssetExtractionDetails>>({
      method: "GET",
      path: `/v1/asset-extractions/${jobId}`,
      ...requestControls(input),
    });
  }

  retryAssetExtraction(jobId: string, input: RequestControls = {}): Promise<ApiEnvelope<AssetExtractionJobRecord>> {
    return this.http.request<ApiEnvelope<AssetExtractionJobRecord>>({
      method: "POST",
      path: `/v1/asset-extractions/${jobId}/retry`,
      ...requestControls(input),
    });
  }

  cancelAssetExtraction(jobId: string, input: RequestControls = {}): Promise<ApiEnvelope<AssetExtractionJobRecord>> {
    return this.http.request<ApiEnvelope<AssetExtractionJobRecord>>({
      method: "POST",
      path: `/v1/asset-extractions/${jobId}/cancel`,
      ...requestControls(input),
    });
  }

  downloadExtractionArtifact(artifactId: string, input: RequestControls = {}): Promise<Uint8Array> {
    return this.http.request<Uint8Array>({
      method: "GET",
      path: `/v1/extraction-artifacts/${artifactId}/download`,
      ...requestControls(input),
      responseType: "bytes",
    });
  }
}

const extractionListQuery = (input: AssetExtractionListInput): JsonObject =>
  withoutUndefined({
    status: input.status,
    limit: input.limit ?? 50,
  }) as JsonObject;
