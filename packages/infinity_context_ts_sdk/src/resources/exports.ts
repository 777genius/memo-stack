import type { RequestExecutor } from "../client.js";
import { MemoryScope, singleScopePayload, withoutUndefined, type SingleScopeInput } from "../payload.js";
import type { JsonObject } from "../types.js";

export class ExportsClient {
  constructor(private readonly http: RequestExecutor) {}

  exportMemoryScopeSnapshot(input: {
    readonly spaceSlug: string;
    readonly memoryScopeExternalRef: string;
    readonly redacted?: boolean;
  }): Promise<JsonObject> {
    return this.http.request<JsonObject>({
      method: "GET",
      path: "/v1/export/memory_scope-snapshot",
      params: {
        space_slug: input.spaceSlug,
        memory_scope_external_ref: input.memoryScopeExternalRef,
        redacted: input.redacted ?? false,
      },
    });
  }

  exportGraph(input: SingleScopeInput & {
    readonly scope?: MemoryScope;
    readonly includeDeleted?: boolean;
    readonly includeRestricted?: boolean;
    readonly maxFacts?: number;
    readonly maxDocuments?: number;
    readonly maxEpisodes?: number;
    readonly maxChunks?: number;
  }): Promise<JsonObject> {
    return this.http.request<JsonObject>({
      method: "GET",
      path: "/v1/export/graph.json",
      params: withoutUndefined({
        ...(input.scope?.toPayload() ?? singleScopePayload(input)),
        include_deleted: input.includeDeleted ?? false,
        include_restricted: input.includeRestricted ?? false,
        max_facts: input.maxFacts ?? 250,
        max_documents: input.maxDocuments ?? 100,
        max_episodes: input.maxEpisodes ?? 100,
        max_chunks: input.maxChunks ?? 500,
      }),
    });
  }

  importMemoryScopeSnapshot(input: {
    readonly spaceSlug: string;
    readonly memoryScopeExternalRef: string;
    readonly snapshot: JsonObject;
    readonly manifest?: JsonObject;
    readonly dryRun?: boolean;
    readonly mergeStrategy?: string;
    readonly confirmed?: boolean;
    readonly sourceName?: string;
  }): Promise<JsonObject> {
    return this.http.request<JsonObject>({
      method: "POST",
      path: "/v1/export/memory_scope-snapshot/import",
      json: withoutUndefined({
        space_slug: input.spaceSlug,
        memory_scope_external_ref: input.memoryScopeExternalRef,
        snapshot: input.snapshot,
        manifest: input.manifest,
        dry_run: input.dryRun ?? true,
        merge_strategy: input.mergeStrategy ?? "fail_on_conflict",
        confirmed: input.confirmed ?? false,
        source_name: input.sourceName ?? "ts-sdk-memory_scope-snapshot",
      }) as JsonObject,
    });
  }

  previewMemoryScopeSnapshotImport(input: {
    readonly spaceSlug: string;
    readonly memoryScopeExternalRef: string;
    readonly snapshot: JsonObject;
    readonly manifest?: JsonObject;
    readonly mergeStrategy?: string;
  }): Promise<JsonObject> {
    return this.http.request<JsonObject>({
      method: "POST",
      path: "/v1/export/memory_scope-snapshot/preview",
      json: withoutUndefined({
        space_slug: input.spaceSlug,
        memory_scope_external_ref: input.memoryScopeExternalRef,
        snapshot: input.snapshot,
        manifest: input.manifest,
        merge_strategy: input.mergeStrategy ?? "fail_on_conflict",
      }) as JsonObject,
    });
  }
}
