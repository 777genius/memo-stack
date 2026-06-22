import { ValueError } from "./payload.js";
import type { FullMemoryProofArtifactPolicy } from "./proof-artifact.js";
import {
  MEMORY_QUALITY_PRESETS,
  type MemoryQualityPresetName,
} from "./workflows/memory-quality-presets.js";

export interface FullMemoryProofArtifactPolicyConfig {
  readonly policy: FullMemoryProofArtifactPolicy;
  readonly requireFullMemory: boolean;
  readonly qualityPreset?: MemoryQualityPresetName;
}

const MEMORY_QUALITY_PRESET_NAMES = ["lite", "durable", "full"] as const satisfies readonly MemoryQualityPresetName[];

export function buildFullMemoryProofArtifactPolicyFromEnv(
  env: Readonly<Record<string, string | undefined>>,
): FullMemoryProofArtifactPolicyConfig {
  const qualityPreset = parseMemoryQualityPresetName(env.INFINITY_CONTEXT_PROOF_QUALITY_PRESET);
  const basePolicy = qualityPreset === undefined
    ? {
        requireOk: true,
        requireFullMemory: true,
      } satisfies FullMemoryProofArtifactPolicy
    : MEMORY_QUALITY_PRESETS[qualityPreset].proofArtifact;
  const requireFullMemory = parseBoolean(
    env.INFINITY_CONTEXT_PROOF_REQUIRE_FULL_MEMORY,
    basePolicy.requireFullMemory ?? true,
  );
  const policy: FullMemoryProofArtifactPolicy = {
    ...basePolicy,
    requireFullMemory,
    ...numberPolicy("maxFailedChecks", env.INFINITY_CONTEXT_PROOF_MAX_FAILED_CHECKS, parseNonNegativeInteger),
    ...numberPolicy("minChecksPassed", env.INFINITY_CONTEXT_PROOF_MIN_CHECKS_PASSED, parseNonNegativeInteger),
    ...numberPolicy(
      "minSourceEvidenceSuccessRate",
      env.INFINITY_CONTEXT_PROOF_MIN_SOURCE_EVIDENCE_SUCCESS_RATE,
      parseUnitInterval,
    ),
    ...numberPolicy(
      "maxMemoryInspectionIssues",
      env.INFINITY_CONTEXT_PROOF_MAX_MEMORY_INSPECTION_ISSUES,
      parseNonNegativeInteger,
    ),
    ...numberPolicy(
      "maxMaintenanceActionable",
      env.INFINITY_CONTEXT_PROOF_MAX_MAINTENANCE_ACTIONABLE,
      parseNonNegativeInteger,
    ),
    ...numberPolicy("maxOutboxBlocking", env.INFINITY_CONTEXT_PROOF_MAX_OUTBOX_BLOCKING, parseNonNegativeInteger),
    ...numberPolicy("maxDurationMs", env.INFINITY_CONTEXT_PROOF_MAX_DURATION_MS, parseNonNegativeInteger),
    ...csvPolicy("requiredAdapters", env.INFINITY_CONTEXT_PROOF_REQUIRED_ADAPTERS),
    ...csvPolicy("requiredRetrievalSources", env.INFINITY_CONTEXT_PROOF_REQUIRED_RETRIEVAL_SOURCES),
    ...booleanPolicy("requireGitCommit", env.INFINITY_CONTEXT_PROOF_REQUIRE_GIT_COMMIT),
    ...booleanPolicy("requirePackageVersion", env.INFINITY_CONTEXT_PROOF_REQUIRE_PACKAGE_VERSION),
  };

  return {
    policy,
    requireFullMemory,
    ...(qualityPreset === undefined ? {} : { qualityPreset }),
  };
}

function parseMemoryQualityPresetName(value: string | undefined): MemoryQualityPresetName | undefined {
  if (value === undefined || value.trim().length === 0) {
    return undefined;
  }
  const normalized = value.trim();
  if (isMemoryQualityPresetName(normalized)) {
    return normalized;
  }

  throw new ValueError(
    `INFINITY_CONTEXT_PROOF_QUALITY_PRESET must be one of: ${MEMORY_QUALITY_PRESET_NAMES.join(", ")}`,
  );
}

function isMemoryQualityPresetName(value: string): value is MemoryQualityPresetName {
  return (MEMORY_QUALITY_PRESET_NAMES as readonly string[]).includes(value);
}

function parseNonNegativeInteger(value: string | undefined): number | undefined {
  if (value === undefined) {
    return undefined;
  }
  const parsed = Number(value);

  return Number.isInteger(parsed) && parsed >= 0 ? parsed : undefined;
}

function parseNonNegativeNumber(value: string | undefined): number | undefined {
  if (value === undefined) {
    return undefined;
  }
  const parsed = Number(value);

  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
}

function parseBoolean(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined) {
    return fallback;
  }
  return !["0", "false", "no"].includes(value.toLowerCase());
}

function parseUnitInterval(value: string | undefined): number | undefined {
  const parsed = parseNonNegativeNumber(value);

  return parsed !== undefined && parsed <= 1 ? parsed : undefined;
}

function numberPolicy<TKey extends keyof FullMemoryProofArtifactPolicy>(
  outputKey: TKey,
  value: string | undefined,
  parse: (value: string | undefined) => number | undefined,
): Pick<FullMemoryProofArtifactPolicy, TKey> | Record<string, never> {
  const parsed = parse(value);

  return parsed === undefined ? {} : { [outputKey]: parsed } as Pick<FullMemoryProofArtifactPolicy, TKey>;
}

function booleanPolicy<TKey extends keyof FullMemoryProofArtifactPolicy>(
  outputKey: TKey,
  value: string | undefined,
): Pick<FullMemoryProofArtifactPolicy, TKey> | Record<string, never> {
  return value === undefined
    ? {}
    : { [outputKey]: parseBoolean(value, false) } as Pick<FullMemoryProofArtifactPolicy, TKey>;
}

function csvPolicy<TKey extends keyof FullMemoryProofArtifactPolicy>(
  outputKey: TKey,
  value: string | undefined,
): Pick<FullMemoryProofArtifactPolicy, TKey> | Record<string, never> {
  if (value === undefined) {
    return {};
  }
  const items = value.split(",").map((item) => item.trim()).filter(Boolean);

  return items.length === 0
    ? {}
    : { [outputKey]: items } as unknown as Pick<FullMemoryProofArtifactPolicy, TKey>;
}
