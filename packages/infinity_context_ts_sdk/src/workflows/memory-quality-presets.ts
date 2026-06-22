import type { FullMemoryProofArtifactPolicy } from "../proof-artifact.js";
import type { MemoryBriefQualityPolicy } from "./memory-brief-quality.js";
import type {
  MemoryInspectionPolicy,
  MemoryInspectionSection,
} from "./memory-inspection-report.js";
import type { MemoryMaintenancePolicy } from "./memory-maintenance-report.js";
import type { MemorySnapshotTransferPolicy } from "./memory-snapshot-transfer-report.js";
import type { MemorySummaryLoopPolicy } from "./memory-summary-loop.js";

export type MemoryQualityPresetName = "lite" | "durable" | "full";

export interface MemoryQualityPreset {
  readonly name: MemoryQualityPresetName;
  readonly description: string;
  readonly brief: MemoryBriefQualityPolicy;
  readonly summaryLoop: MemorySummaryLoopPolicy;
  readonly inspection: MemoryInspectionPolicy;
  readonly maintenance: MemoryMaintenancePolicy;
  readonly snapshotPreview: MemorySnapshotTransferPolicy;
  readonly snapshotImport: MemorySnapshotTransferPolicy;
  readonly proofArtifact: FullMemoryProofArtifactPolicy;
}

export interface MemoryQualityPresetOverrides {
  readonly description?: string;
  readonly brief?: MemoryBriefQualityPolicy;
  readonly summaryLoop?: MemorySummaryLoopPolicy;
  readonly inspection?: MemoryInspectionPolicy;
  readonly maintenance?: MemoryMaintenancePolicy;
  readonly snapshotPreview?: MemorySnapshotTransferPolicy;
  readonly snapshotImport?: MemorySnapshotTransferPolicy;
  readonly proofArtifact?: FullMemoryProofArtifactPolicy;
}

const DURABLE_INSPECTION_SECTIONS = [
  "memoryBrowser",
  "operationsConsole",
  "usage",
  "capabilities",
  "runtimeDiagnostics",
  "snapshot",
  "snapshotPreview",
] as const satisfies readonly MemoryInspectionSection[];

const FULL_INSPECTION_SECTIONS = [
  ...DURABLE_INSPECTION_SECTIONS,
  "graph",
] as const satisfies readonly MemoryInspectionSection[];

const SNAPSHOT_PREVIEW_POLICY = {
  allowedModes: ["preview"],
  forbidMutation: true,
  requireRedacted: true,
  forbidSameScope: true,
  requireManifest: true,
  requirePreview: true,
  maxWarnings: 1,
  requiredMergeStrategy: "fail_on_conflict",
} as const satisfies MemorySnapshotTransferPolicy;

const SNAPSHOT_IMPORT_POLICY = {
  allowedModes: ["confirmed_import"],
  requireMutation: true,
  forbidSameScope: true,
  requireImportResult: true,
  minFacts: 1,
} as const satisfies MemorySnapshotTransferPolicy;

const PRESET_BASES: Readonly<Record<MemoryQualityPresetName, MemoryQualityPreset>> = {
  lite: {
    name: "lite",
    description: "Development and smoke-test quality gates that do not require full durable memory adapters.",
    brief: {
      minContextItems: 1,
      requireSupportedAnswer: true,
    },
    summaryLoop: {
      requireQuality: true,
      minContextItems: 1,
      minUniqueSourceRefs: 1,
    },
    inspection: {
      requireComplete: false,
      maxIssues: 5,
    },
    maintenance: {
      requireComplete: false,
      maxIssues: 5,
    },
    snapshotPreview: SNAPSHOT_PREVIEW_POLICY,
    snapshotImport: SNAPSHOT_IMPORT_POLICY,
    proofArtifact: {
      requireOk: true,
      requireFullMemory: false,
      maxFailedChecks: 0,
    },
  },
  durable: {
    name: "durable",
    description: "Beta-ready durable runtime gates for Postgres-backed memory with source evidence and outbox proof.",
    brief: {
      minContextItems: 1,
      requireSearch: true,
      minSearchItems: 1,
      requireDigest: true,
      minDigestSections: 1,
      minDigestSourceRefs: 1,
      requireSupportedAnswer: true,
    },
    summaryLoop: {
      requireReadiness: true,
      requireSourceEvidence: true,
      requireOutboxDrain: true,
      requireQuality: true,
      minSourceEvidenceSuccessRate: 1,
      maxSourceEvidenceFailures: 0,
      minContextItems: 1,
      minSearchItems: 1,
      minDigestSections: 1,
      minTopEvidenceItems: 1,
      minUniqueSourceRefs: 1,
      minCitations: 1,
    },
    inspection: {
      requireComplete: true,
      maxIssues: 0,
      requiredSections: DURABLE_INSPECTION_SECTIONS,
      maxOperationExtractionJobs: 0,
      maxOperationContextLinkSuggestions: 0,
    },
    maintenance: {
      requireComplete: true,
      maxIssues: 0,
      maxHighPriorityActions: 0,
      maxExtractionJobs: 0,
    },
    snapshotPreview: SNAPSHOT_PREVIEW_POLICY,
    snapshotImport: SNAPSHOT_IMPORT_POLICY,
    proofArtifact: {
      requireOk: true,
      requireFullMemory: false,
      maxFailedChecks: 0,
      minSourceEvidenceSuccessRate: 1,
      maxMemoryInspectionIssues: 0,
      maxOutboxBlocking: 0,
      requireGitCommit: true,
      requirePackageVersion: true,
    },
  },
  full: {
    name: "full",
    description: "Release-grade full-memory gates that require durable storage, Qdrant, Graphiti and derived retrieval.",
    brief: {
      minContextItems: 1,
      requireSearch: true,
      minSearchItems: 1,
      requireDigest: true,
      minDigestSections: 1,
      minDigestSourceRefs: 1,
      requireSupportedAnswer: true,
      requireDerivedRetrieval: true,
      requiredRetrieval: ["vector", "graph"],
    },
    summaryLoop: {
      requireReadiness: true,
      requireSourceEvidence: true,
      requireOutboxDrain: true,
      requireQuality: true,
      minSourceEvidenceSuccessRate: 1,
      maxSourceEvidenceFailures: 0,
      minContextItems: 1,
      minSearchItems: 1,
      minDigestSections: 1,
      minTopEvidenceItems: 1,
      minUniqueSourceRefs: 2,
      minCitations: 1,
      requireDerivedRetrieval: true,
      requiredRetrieval: ["vector", "graph"],
    },
    inspection: {
      requireComplete: true,
      maxIssues: 0,
      requiredSections: FULL_INSPECTION_SECTIONS,
      requiredAdapters: ["qdrant", "graphiti"],
      maxOperationExtractionJobs: 0,
      maxOperationContextLinkSuggestions: 0,
    },
    maintenance: {
      requireComplete: true,
      maxIssues: 0,
      maxTotalActionable: 0,
    },
    snapshotPreview: SNAPSHOT_PREVIEW_POLICY,
    snapshotImport: SNAPSHOT_IMPORT_POLICY,
    proofArtifact: {
      requireOk: true,
      requireFullMemory: true,
      maxFailedChecks: 0,
      minSourceEvidenceSuccessRate: 1,
      maxMemoryInspectionIssues: 0,
      maxMaintenanceActionable: 0,
      maxOutboxBlocking: 0,
      requiredAdapters: ["qdrant", "graphiti"],
      requiredRetrievalSources: ["vector", "graph"],
      requireGitCommit: true,
      requirePackageVersion: true,
    },
  },
};

export const MEMORY_QUALITY_PRESETS = freezePresetRecord({
  lite: createMemoryQualityPreset("lite"),
  durable: createMemoryQualityPreset("durable"),
  full: createMemoryQualityPreset("full"),
});

export function createMemoryQualityPreset(
  name: MemoryQualityPresetName,
  overrides: MemoryQualityPresetOverrides = {},
): MemoryQualityPreset {
  const base = PRESET_BASES[name];

  return freezePreset({
    name: base.name,
    description: overrides.description ?? base.description,
    brief: mergePolicy(base.brief, overrides.brief),
    summaryLoop: mergePolicy(base.summaryLoop, overrides.summaryLoop),
    inspection: mergePolicy(base.inspection, overrides.inspection),
    maintenance: mergePolicy(base.maintenance, overrides.maintenance),
    snapshotPreview: mergePolicy(base.snapshotPreview, overrides.snapshotPreview),
    snapshotImport: mergePolicy(base.snapshotImport, overrides.snapshotImport),
    proofArtifact: mergePolicy(base.proofArtifact, overrides.proofArtifact),
  });
}

function mergePolicy<TPolicy extends object>(
  base: TPolicy,
  overrides: TPolicy | undefined,
): TPolicy {
  return {
    ...base,
    ...(overrides ?? {}),
  };
}

function freezePresetRecord(
  presets: Readonly<Record<MemoryQualityPresetName, MemoryQualityPreset>>,
): Readonly<Record<MemoryQualityPresetName, MemoryQualityPreset>> {
  return Object.freeze(presets);
}

function freezePreset(preset: MemoryQualityPreset): MemoryQualityPreset {
  return Object.freeze({
    ...preset,
    brief: freezePolicy(preset.brief),
    summaryLoop: freezePolicy(preset.summaryLoop),
    inspection: freezePolicy(preset.inspection),
    maintenance: freezePolicy(preset.maintenance),
    snapshotPreview: freezePolicy(preset.snapshotPreview),
    snapshotImport: freezePolicy(preset.snapshotImport),
    proofArtifact: freezePolicy(preset.proofArtifact),
  });
}

function freezePolicy<TPolicy extends object>(policy: TPolicy): TPolicy {
  const copy = { ...policy } as Record<string, unknown>;
  for (const [key, value] of Object.entries(copy)) {
    copy[key] = Array.isArray(value) ? Object.freeze([...value]) : value;
  }

  return Object.freeze(copy) as TPolicy;
}
