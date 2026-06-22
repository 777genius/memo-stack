import type { MemoryBriefDiagnostics, RunMemorySummaryLoopResult } from "./memory.js";
import type {
  MemoryBriefEvidenceSummary,
  MemoryBriefQualityReport,
} from "./memory-brief-quality.js";
import type {
  RecordSourceEvidenceBatchSummary,
} from "./memory-source-evidence.js";
import { uniqueStrings } from "./workflow-helpers.js";

export type MemorySummaryLoopStatus = "ready" | "degraded" | "failed";
export type MemorySummaryLoopGateStatus = "passed" | "failed" | "skipped";

export interface MemorySummaryLoopGateReport {
  readonly status: MemorySummaryLoopGateStatus;
  readonly ok: boolean | null;
  readonly errors: readonly string[];
  readonly warnings: readonly string[];
}

export interface MemorySummaryLoopSourceEvidenceReport {
  readonly total: number;
  readonly completed: number;
  readonly skipped: number;
  readonly succeeded: number;
  readonly failed: number;
  readonly successRate: number;
  readonly retryableFailures: number;
  readonly nonRetryableFailures: number;
  readonly bySourceType: Readonly<Record<string, number>>;
}

export interface MemorySummaryLoopReadableSummary {
  readonly contextItems: number;
  readonly searchItems: number;
  readonly digestSections: number;
  readonly topEvidenceItems: number;
  readonly sourceRefsTotal: number;
  readonly uniqueSourceRefs: number;
  readonly citationsTotal: number;
  readonly uniqueCitations: number;
  readonly bySourceType: Readonly<Record<string, number>>;
  readonly renderedText: string;
  readonly renderedMarkdown?: string;
}

export interface MemorySummaryLoopReport {
  readonly ok: boolean;
  readonly status: MemorySummaryLoopStatus;
  readonly gates: {
    readonly readiness: MemorySummaryLoopGateReport;
    readonly sourceEvidence: MemorySummaryLoopGateReport;
    readonly outboxDrain: MemorySummaryLoopGateReport;
    readonly quality: MemorySummaryLoopGateReport;
  };
  readonly sourceEvidence?: MemorySummaryLoopSourceEvidenceReport;
  readonly quality?: MemoryBriefQualityReport;
  readonly evidence: MemoryBriefEvidenceSummary;
  readonly retrieval: MemoryBriefDiagnostics;
  readonly summary: MemorySummaryLoopReadableSummary;
  readonly warnings: readonly string[];
  readonly errors: readonly string[];
}

export function summarizeMemorySummaryLoop(loop: RunMemorySummaryLoopResult): MemorySummaryLoopReport {
  const errors = uniqueStrings([
    ...(loop.readiness?.readiness.errors ?? []),
    ...sourceEvidenceErrors(loop.sourceEvidenceSummary),
    ...outboxDrainErrors(loop),
    ...(loop.quality?.errors ?? []),
  ]);
  const warnings = uniqueStrings([
    ...loop.diagnostics.warnings,
    ...(loop.readiness?.readiness.warnings ?? []),
    ...(loop.quality?.warnings ?? []),
    ...loop.evidenceSummary.warnings,
  ]);

  return {
    ok: loop.diagnostics.ok,
    status: loopStatus(loop, errors),
    gates: {
      readiness: gateReport(
        loop.diagnostics.readinessOk,
        loop.readiness?.readiness.errors,
        loop.readiness?.readiness.warnings,
      ),
      sourceEvidence: gateReport(loop.diagnostics.sourceEvidenceOk, sourceEvidenceErrors(loop.sourceEvidenceSummary)),
      outboxDrain: gateReport(loop.diagnostics.outboxDrainOk, outboxDrainErrors(loop)),
      quality: gateReport(loop.diagnostics.qualityOk, loop.quality?.errors, loop.quality?.warnings),
    },
    ...(loop.sourceEvidenceSummary ? { sourceEvidence: sourceEvidenceReport(loop.sourceEvidenceSummary) } : {}),
    ...(loop.quality ? { quality: loop.quality } : {}),
    evidence: loop.evidenceSummary,
    retrieval: loop.brief.diagnostics,
    summary: readableSummary(loop),
    warnings,
    errors,
  };
}

function loopStatus(loop: RunMemorySummaryLoopResult, errors: readonly string[]): MemorySummaryLoopStatus {
  if (!loop.diagnostics.ok || errors.length > 0) {
    return "failed";
  }
  return loop.diagnostics.warnings.length > 0 || loop.evidenceSummary.warnings.length > 0 ? "degraded" : "ready";
}

function gateReport(
  ok: boolean | null,
  errors: readonly string[] = [],
  warnings: readonly string[] = [],
): MemorySummaryLoopGateReport {
  return {
    ok,
    status: ok === null ? "skipped" : ok ? "passed" : "failed",
    errors,
    warnings,
  };
}

function sourceEvidenceReport(summary: RecordSourceEvidenceBatchSummary): MemorySummaryLoopSourceEvidenceReport {
  return {
    total: summary.total,
    completed: summary.completed,
    skipped: summary.skipped,
    succeeded: summary.succeeded,
    failed: summary.failed,
    successRate: summary.successRate,
    retryableFailures: summary.retryableFailures,
    nonRetryableFailures: summary.nonRetryableFailures,
    bySourceType: summary.bySourceType,
  };
}

function sourceEvidenceErrors(summary: RecordSourceEvidenceBatchSummary | undefined): readonly string[] {
  if (summary === undefined || (summary.failed === 0 && !summary.stopped)) {
    return [];
  }

  return [
    `source evidence batch failed ${summary.failed} item(s), skipped ${summary.skipped} item(s)`,
  ];
}

function outboxDrainErrors(loop: RunMemorySummaryLoopResult): readonly string[] {
  const outbox = loop.outboxDrain;
  if (outbox === undefined || loop.diagnostics.outboxDrainOk !== false) {
    return [];
  }

  return [
    `outbox still has ${outbox.diagnostics.blocking_count} blocking item(s) after ${outbox.diagnostics.attempts} attempt(s)`,
  ];
}

function readableSummary(loop: RunMemorySummaryLoopResult): MemorySummaryLoopReadableSummary {
  return {
    contextItems: loop.evidenceSummary.contextItems,
    searchItems: loop.evidenceSummary.searchItems,
    digestSections: loop.evidenceSummary.digestSections,
    topEvidenceItems: loop.evidenceSummary.topEvidenceItems,
    sourceRefsTotal: loop.evidenceSummary.sourceRefsTotal,
    uniqueSourceRefs: loop.evidenceSummary.uniqueSourceRefs,
    citationsTotal: loop.evidenceSummary.citationsTotal,
    uniqueCitations: loop.evidenceSummary.uniqueCitations,
    bySourceType: loop.evidenceSummary.bySourceType,
    renderedText: loop.brief.context.data.rendered_text,
    ...(loop.brief.digest ? { renderedMarkdown: loop.brief.digest.data.rendered_markdown } : {}),
  };
}
