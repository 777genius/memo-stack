import { InfinityContextClient } from "./infinity-context-client.js";
import type { ContextBundleData, ContextDiagnostics, ContextEnvelope } from "./context-types.js";
import {
  healthyRetrievalComponents,
  retrievalDiagnostics,
  usedDerivedRetrieval,
  type ContextRetrievalDiagnostics,
} from "./diagnostics.js";
import { InfinityContextError } from "./errors.js";
import { ReadScope } from "./payload.js";
import type { DocumentRecord, FactRecord, InfinityContextCapabilities, JsonObject, MemoryScopeRecord, Space } from "./types.js";

export interface FullMemoryProofOptions {
  readonly client: InfinityContextClient;
  readonly runId?: string | undefined;
  readonly requireFullMemory?: boolean | undefined;
  readonly pollAttempts?: number | undefined;
  readonly pollDelayMs?: number | undefined;
  readonly sleep?: ((ms: number) => Promise<void>) | undefined;
  readonly now?: (() => Date) | undefined;
}

export interface FullMemoryProofReport {
  readonly ok: boolean;
  readonly runId: string;
  readonly spaceSlug: string;
  readonly memoryScopeExternalRefs: readonly string[];
  readonly checks: {
    readonly capabilitiesFullMemory: boolean;
    readonly contextReturnedEvidence: boolean;
    readonly searchReturnedEvidence: boolean;
    readonly digestReturnedEvidence: boolean;
    readonly contextLinkCreated: boolean;
    readonly derivedRetrievalUsed: boolean;
    readonly vectorHealthy: boolean;
    readonly graphHealthy: boolean;
  };
  readonly created: {
    readonly spaceId: string;
    readonly memoryScopeIds: readonly string[];
    readonly factIds: readonly string[];
    readonly documentId: string;
    readonly episodeId: string;
    readonly contextLinkId: string;
  };
  readonly capabilities: {
    readonly enabledAdapters: readonly string[];
    readonly supportsQdrant: boolean;
    readonly supportsGraphiti: boolean;
  };
  readonly retrieval: {
    readonly vector: ContextRetrievalDiagnostics;
    readonly graph: ContextRetrievalDiagnostics;
    readonly rag: ContextRetrievalDiagnostics;
  };
  readonly contextDiagnostics: ContextDiagnostics;
  readonly searchDiagnostics: ContextDiagnostics;
  readonly digestDiagnostics: JsonObject;
}

const defaultPollAttempts = 6;
const defaultPollDelayMs = 2_000;

export async function runFullMemoryProof(options: FullMemoryProofOptions): Promise<FullMemoryProofReport> {
  const now = options.now ?? (() => new Date());
  const runId = safeRunId(options.runId ?? `sdk-${now().toISOString()}`);
  const spaceSlug = `sdk-full-memory-proof:${runId}`;
  const memoryScopeExternalRefs = [
    "workspace-global",
    "topic:full-memory-proof:feedback",
    "source:full-memory-proof-transcript",
  ] as const;
  const readScope = ReadScope.external({
    spaceSlug,
    memoryScopeExternalRefs,
  });
  const capabilities = await options.client.system.capabilities();
  const capabilitiesFullMemory = hasFullMemoryCapabilities(capabilities);
  const space = await ensureSpace(options.client, {
    slug: spaceSlug,
    name: `SDK full memory proof ${runId}`,
  });
  const scopes = await Promise.all(
    memoryScopeExternalRefs.map((externalRef) =>
      ensureMemoryScope(options.client, {
        spaceId: space.id,
        externalRef,
        name: externalRef,
      }),
    ),
  );

  const facts = await Promise.all([
    options.client.facts.rememberFact({
      spaceSlug,
      memoryScopeExternalRef: "workspace-global",
      text: `${runId}: Qdrant owns vector recall, Graphiti owns temporal graph memory, and OpenAI embeddings create derived retrieval vectors.`,
      kind: "architecture_decision",
      category: "full_memory_proof",
      tags: ["full-memory-proof", "qdrant", "graphiti", "openai-embeddings"],
      ttlPolicy: "durable",
      sourceRefs: [{ source_type: "sdk-full-memory-proof", source_id: `${runId}:architecture` }],
      idempotencyKey: `${runId}:fact:architecture`,
    }),
    options.client.facts.rememberFact({
      spaceSlug,
      memoryScopeExternalRef: "topic:full-memory-proof:feedback",
      text: `${runId}: User prefers concise summaries that call out source freshness, degraded retrieval, and missing evidence.`,
      kind: "summary_feedback",
      category: "summary_preference",
      tags: ["full-memory-proof", "summary-feedback"],
      ttlPolicy: "durable",
      sourceRefs: [{ source_type: "sdk-full-memory-proof", source_id: `${runId}:feedback` }],
      idempotencyKey: `${runId}:fact:feedback`,
    }),
  ]);
  const document = await options.client.documents.ingestDocument({
    spaceSlug,
    memoryScopeExternalRef: "source:full-memory-proof-transcript",
    title: `${runId} full memory source note`,
    text: [
      `${runId}: Durable source note for full memory proof.`,
      "The monitoring product should retrieve daily social intelligence through Qdrant vector recall and Graphiti temporal graph recall.",
      "The summary should mention freshness, degraded provider evidence, and concise operator action.",
    ].join("\n"),
    sourceExternalId: `${runId}:document`,
    sourceType: "sdk-full-memory-proof",
    classification: "internal",
    sourceRefs: [{ source_type: "sdk-full-memory-proof", source_id: `${runId}:document` }],
    idempotencyKey: `${runId}:document`,
  });
  await options.client.documents.processDocument(document.data.id, {
    idempotencyKey: `${runId}:document:process`,
  });
  const episode = await options.client.documents.ingestEpisode({
    spaceSlug,
    memoryScopeExternalRef: "source:full-memory-proof-transcript",
    sourceExternalId: `${runId}:episode`,
    sourceType: "sdk-full-memory-proof",
    text: `${runId}: Later update: Graphiti should preserve temporal changes while Qdrant handles semantic document recall.`,
    occurredAt: now().toISOString(),
    speaker: "sdk-proof",
    trustLevel: "high",
    kindHint: "decision_update",
    metadata: { run_id: runId },
    idempotencyKey: `${runId}:episode`,
  });
  const contextLink = await options.client.contextLinks.createContextLink({
    spaceSlug,
    memoryScopeExternalRef: "source:full-memory-proof-transcript",
    sourceType: "document",
    sourceId: document.data.id,
    targetType: "fact",
    targetId: facts[0]?.data.id ?? "unknown",
    relationType: "supports",
    confidence: "high",
    reason: `${runId}: SDK proof links document evidence to durable architecture fact.`,
    metadata: { run_id: runId, proof: "full-memory" },
  });

  const query = `${runId} Qdrant Graphiti OpenAI embeddings concise summary freshness degraded retrieval`;
  const context = await pollContext(options, () =>
    options.client.context.buildContext({
      query,
      readScope,
      tokenBudget: 1800,
      maxFacts: 20,
      maxChunks: 20,
      maxEvidenceItems: 5,
      consistencyMode: "best_effort",
      includeStale: false,
    }),
  );
  const search = await options.client.context.search({
    query,
    readScope,
    tokenBudget: 1200,
    maxFacts: 20,
    maxChunks: 20,
    maxEvidenceItems: 5,
    consistencyMode: "best_effort",
    includeStale: false,
  });
  const digest = await options.client.context.buildDigest({
    topic: `${runId} full memory product summary`,
    readScope,
    tokenBudget: 2200,
    maxFacts: 20,
    maxChunks: 20,
    maxSuggestions: 5,
    includeRelated: true,
    format: "markdown",
  });
  const contextDiagnostics = context.data.diagnostics;
  const checks = {
    capabilitiesFullMemory,
    contextReturnedEvidence: context.data.items.length > 0 || context.data.rendered_text.includes(runId),
    searchReturnedEvidence: search.data.items.length > 0,
    digestReturnedEvidence: digest.data.rendered_markdown.includes(runId) || digest.data.sections.length > 0,
    contextLinkCreated: contextLink.data.id.length > 0,
    derivedRetrievalUsed: usedDerivedRetrieval(contextDiagnostics),
    vectorHealthy: healthyRetrievalComponents(contextDiagnostics, ["vector"]),
    graphHealthy: healthyRetrievalComponents(contextDiagnostics, ["graph"]),
  };
  const requireFullMemory = options.requireFullMemory ?? true;

  return {
    ok: Object.values(checks).every(Boolean) || (!requireFullMemory && checks.contextReturnedEvidence),
    runId,
    spaceSlug,
    memoryScopeExternalRefs,
    checks,
    created: {
      spaceId: space.id,
      memoryScopeIds: scopes.map((scope) => scope.id),
      factIds: facts.map((fact) => fact.data.id),
      documentId: document.data.id,
      episodeId: stringField(episode.data, "id") ?? stringField(episode.data, "episode_id") ?? "unknown",
      contextLinkId: contextLink.data.id,
    },
    capabilities: {
      enabledAdapters: capabilities.enabled_adapters ?? [],
      supportsQdrant: capabilities.supports_qdrant === true,
      supportsGraphiti: capabilities.supports_graphiti === true,
    },
    retrieval: {
      vector: retrievalDiagnostics(contextDiagnostics, "vector"),
      graph: retrievalDiagnostics(contextDiagnostics, "graph"),
      rag: retrievalDiagnostics(contextDiagnostics, "rag"),
    },
    contextDiagnostics,
    searchDiagnostics: search.data.diagnostics,
    digestDiagnostics: digest.data.diagnostics,
  };
}

async function ensureSpace(
  client: InfinityContextClient,
  input: { readonly slug: string; readonly name: string },
): Promise<Space> {
  const existing = await client.spaces.listSpaces({ limit: 500 });
  const found = existing.data.find((space) => space.slug === input.slug);
  if (found !== undefined) {
    return found;
  }

  try {
    return (await client.spaces.createSpace(input)).data;
  } catch (error) {
    if (!isConflict(error)) {
      throw error;
    }
    const afterConflict = await client.spaces.listSpaces({ limit: 500 });
    const created = afterConflict.data.find((space) => space.slug === input.slug);
    if (created === undefined) {
      throw error;
    }
    return created;
  }
}

async function ensureMemoryScope(
  client: InfinityContextClient,
  input: { readonly spaceId: string; readonly externalRef: string; readonly name: string },
): Promise<MemoryScopeRecord> {
  const existing = await client.spaces.listMemoryScopes({ spaceId: input.spaceId, limit: 500 });
  const found = existing.data.find((scope) => scope.external_ref === input.externalRef);
  if (found !== undefined) {
    return found;
  }

  try {
    return (await client.spaces.createMemoryScope(input)).data;
  } catch (error) {
    if (!isConflict(error)) {
      throw error;
    }
    const afterConflict = await client.spaces.listMemoryScopes({ spaceId: input.spaceId, limit: 500 });
    const created = afterConflict.data.find((scope) => scope.external_ref === input.externalRef);
    if (created === undefined) {
      throw error;
    }
    return created;
  }
}

async function pollContext(
  options: FullMemoryProofOptions,
  build: () => Promise<ContextEnvelope<ContextBundleData>>,
): Promise<ContextEnvelope<ContextBundleData>> {
  const attempts = positiveIntegerOr(options.pollAttempts, defaultPollAttempts);
  const delayMs = positiveIntegerOr(options.pollDelayMs, defaultPollDelayMs);
  const sleep = options.sleep ?? defaultSleep;
  let latest: ContextEnvelope<ContextBundleData> | undefined;

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    latest = await build();
    if (latest.data.items.length > 0 || latest.data.rendered_text.trim().length > 0) {
      return latest;
    }
    if (attempt + 1 < attempts) {
      await sleep(delayMs);
    }
  }

  return latest ?? await build();
}

function hasFullMemoryCapabilities(capabilities: InfinityContextCapabilities): boolean {
  const enabled = new Set(capabilities.enabled_adapters ?? []);

  return capabilities.supports_qdrant === true &&
    capabilities.supports_graphiti === true &&
    enabled.has("qdrant") &&
    enabled.has("graphiti");
}

function isConflict(error: unknown): boolean {
  return error instanceof InfinityContextError && error.statusCode === 409;
}

function safeRunId(value: string): string {
  const sanitized = value.toLowerCase().replace(/[^a-z0-9._:-]+/gu, "-").replace(/^-+|-+$/gu, "");

  return sanitized.length === 0 ? "sdk-proof" : sanitized.slice(0, 80);
}

function positiveIntegerOr(value: number | undefined, fallback: number): number {
  return value !== undefined && Number.isInteger(value) && value > 0 ? value : fallback;
}

function stringField(value: JsonObject, key: string): string | undefined {
  const item = value[key];

  return typeof item === "string" ? item : undefined;
}

function defaultSleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
