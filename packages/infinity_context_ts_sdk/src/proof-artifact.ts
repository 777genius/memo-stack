import type { FullMemoryProofReport } from "./full-memory-proof.js";
import type { JsonObject } from "./types.js";

export const FULL_MEMORY_PROOF_ARTIFACT_SCHEMA = "infinity_context.full_memory_proof_artifact.v1";

export interface FullMemoryProofSdkMetadata {
  readonly packageName?: string;
  readonly packageVersion?: string;
}

export interface FullMemoryProofGitMetadata {
  readonly commitSha?: string;
  readonly branch?: string;
  readonly repository?: string;
}

export interface FullMemoryProofRuntimeMetadata {
  readonly baseUrl?: string;
  readonly profile?: string;
  readonly requireFullMemory?: boolean;
}

export interface FullMemoryProofArtifactMetadata {
  readonly sdk?: FullMemoryProofSdkMetadata;
  readonly git?: FullMemoryProofGitMetadata;
  readonly runtime?: FullMemoryProofRuntimeMetadata;
  readonly labels?: JsonObject;
}

export interface FullMemoryProofArtifactInput {
  readonly report: FullMemoryProofReport;
  readonly startedAt?: Date | string;
  readonly finishedAt?: Date | string;
  readonly durationMs?: number;
  readonly metadata?: FullMemoryProofArtifactMetadata;
}

export interface FullMemoryProofArtifactSummary {
  readonly ok: boolean;
  readonly mode: "full" | "lite";
  readonly durableOk: boolean;
  readonly fullMemoryOk: boolean;
  readonly checksTotal: number;
  readonly checksPassed: number;
  readonly checksFailed: number;
  readonly failedChecks: readonly string[];
  readonly enabledAdapters: readonly string[];
  readonly supportsQdrant: boolean;
  readonly supportsGraphiti: boolean;
  readonly vectorHealthy: boolean;
  readonly graphHealthy: boolean;
  readonly derivedRetrievalUsed: boolean;
  readonly retrievalSourcesUsed: readonly string[];
  readonly vectorQueryCount: number;
  readonly graphQueryCount: number;
  readonly ragQueryCount: number;
  readonly sourceEvidenceSuccessRate: number;
  readonly memoryInspectionIssueCount: number;
  readonly maintenanceActionableCount: number;
  readonly outboxBlockingCount: number;
}

export interface FullMemoryProofArtifact {
  readonly schemaVersion: typeof FULL_MEMORY_PROOF_ARTIFACT_SCHEMA;
  readonly generatedAt: string;
  readonly startedAt: string | null;
  readonly finishedAt: string | null;
  readonly durationMs: number | null;
  readonly ok: boolean;
  readonly summary: FullMemoryProofArtifactSummary;
  readonly metadata: FullMemoryProofArtifactMetadata;
  readonly report: FullMemoryProofReport;
}

const fullMemoryCheckNames = new Set([
  "capabilitiesFullMemory",
  "derivedRetrievalUsed",
  "vectorHealthy",
  "graphHealthy",
]);

export function buildFullMemoryProofArtifact(
  input: FullMemoryProofArtifactInput,
): FullMemoryProofArtifact {
  const startedAt = normalizeDate(input.startedAt);
  const finishedAt = normalizeDate(input.finishedAt);
  const generatedAt = finishedAt ?? normalizeDate(new Date()) ?? new Date(0).toISOString();

  return {
    schemaVersion: FULL_MEMORY_PROOF_ARTIFACT_SCHEMA,
    generatedAt,
    startedAt,
    finishedAt,
    durationMs: proofDurationMs(input.durationMs, startedAt, finishedAt),
    ok: input.report.ok,
    summary: summarizeFullMemoryProofReport(input.report),
    metadata: input.metadata ?? {},
    report: input.report,
  };
}

export function summarizeFullMemoryProofReport(
  report: FullMemoryProofReport,
): FullMemoryProofArtifactSummary {
  const checkEntries = Object.entries(report.checks);
  const failedChecks = checkEntries
    .filter(([, passed]) => !passed)
    .map(([name]) => name)
    .sort();
  const durableEntries = checkEntries.filter(([name]) => !fullMemoryCheckNames.has(name));
  const fullMemoryEntries = checkEntries.filter(([name]) => fullMemoryCheckNames.has(name));
  const fullMemoryOk = fullMemoryEntries.every(([, passed]) => passed);

  return {
    ok: report.ok,
    mode: fullMemoryOk ? "full" : "lite",
    durableOk: durableEntries.every(([, passed]) => passed),
    fullMemoryOk,
    checksTotal: checkEntries.length,
    checksPassed: checkEntries.length - failedChecks.length,
    checksFailed: failedChecks.length,
    failedChecks,
    enabledAdapters: report.capabilities.enabledAdapters,
    supportsQdrant: report.capabilities.supportsQdrant,
    supportsGraphiti: report.capabilities.supportsGraphiti,
    vectorHealthy: report.checks.vectorHealthy,
    graphHealthy: report.checks.graphHealthy,
    derivedRetrievalUsed: report.checks.derivedRetrievalUsed,
    retrievalSourcesUsed: stringArrayField(report.contextDiagnostics, "retrieval_sources_used"),
    vectorQueryCount: queryCount(report.retrieval.vector.queryCount),
    graphQueryCount: queryCount(report.retrieval.graph.queryCount),
    ragQueryCount: queryCount(report.retrieval.rag.queryCount),
    sourceEvidenceSuccessRate: report.observed.sourceEvidenceBatchSummary.successRate,
    memoryInspectionIssueCount: report.observed.memoryInspectionIssueCount,
    maintenanceActionableCount: report.observed.maintenanceActionableCount,
    outboxBlockingCount: report.observed.outboxDrainDiagnostics.blocking_count,
  };
}

function normalizeDate(value: Date | string | undefined): string | null {
  if (value === undefined) {
    return null;
  }
  const date = value instanceof Date ? value : new Date(value);
  const timestamp = date.getTime();

  return Number.isFinite(timestamp) ? date.toISOString() : null;
}

function proofDurationMs(
  explicitDurationMs: number | undefined,
  startedAt: string | null,
  finishedAt: string | null,
): number | null {
  if (explicitDurationMs !== undefined && Number.isFinite(explicitDurationMs) && explicitDurationMs >= 0) {
    return Math.round(explicitDurationMs);
  }
  if (startedAt === null || finishedAt === null) {
    return null;
  }
  const durationMs = Date.parse(finishedAt) - Date.parse(startedAt);

  return Number.isFinite(durationMs) ? Math.max(0, durationMs) : null;
}

function stringArrayField(value: JsonObject, key: string): readonly string[] {
  const field = value[key];
  if (!Array.isArray(field)) {
    return [];
  }

  return field.filter((item): item is string => typeof item === "string");
}

function queryCount(value: number | undefined): number {
  return value === undefined ? 0 : value;
}
