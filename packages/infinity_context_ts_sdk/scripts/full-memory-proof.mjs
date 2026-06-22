#!/usr/bin/env node
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import {
  buildFullMemoryProofArtifact,
  evaluateFullMemoryProofArtifact,
  InfinityContextClient,
  runFullMemoryProof,
} from "../dist/index.js";

const env = process.env;
const baseUrl = env.INFINITY_CONTEXT_URL ?? "http://127.0.0.1:7788";
const token = env.INFINITY_CONTEXT_TOKEN;
const outputPath = env.INFINITY_CONTEXT_PROOF_OUTPUT;
const artifactOutputPath = env.INFINITY_CONTEXT_PROOF_ARTIFACT_OUTPUT;
const outputMode = env.INFINITY_CONTEXT_PROOF_OUTPUT_MODE === "artifact" ? "artifact" : "report";
const requireFullMemory = env.INFINITY_CONTEXT_PROOF_REQUIRE_FULL_MEMORY === undefined
  ? true
  : !["0", "false", "no"].includes(env.INFINITY_CONTEXT_PROOF_REQUIRE_FULL_MEMORY.toLowerCase());

const startedAt = new Date();
const report = await runFullMemoryProof({
  client: new InfinityContextClient({
    baseUrl,
    token: () => token,
    timeoutMs: parsePositiveInteger(env.INFINITY_CONTEXT_PROOF_TIMEOUT_MS) ?? 15_000,
    retryPolicy: { maxAttempts: 2 },
  }),
  runId: env.INFINITY_CONTEXT_PROOF_RUN_ID,
  requireFullMemory,
  pollAttempts: parsePositiveInteger(env.INFINITY_CONTEXT_PROOF_POLL_ATTEMPTS),
  pollDelayMs: parsePositiveInteger(env.INFINITY_CONTEXT_PROOF_POLL_DELAY_MS),
  outboxDrainAttempts: parsePositiveInteger(env.INFINITY_CONTEXT_PROOF_OUTBOX_DRAIN_ATTEMPTS),
  outboxDrainDelayMs: parsePositiveInteger(env.INFINITY_CONTEXT_PROOF_OUTBOX_DRAIN_DELAY_MS),
});
const finishedAt = new Date();
const artifact = buildFullMemoryProofArtifact({
  report,
  startedAt,
  finishedAt,
  metadata: {
    sdk: await readPackageMetadata(),
    git: gitMetadata(env),
    runtime: {
      baseUrl,
      requireFullMemory,
      ...(env.INFINITY_CONTEXT_PROOF_RUNTIME_PROFILE !== undefined
        ? { profile: env.INFINITY_CONTEXT_PROOF_RUNTIME_PROFILE }
        : {}),
    },
  },
});
const artifactEvaluation = evaluateFullMemoryProofArtifact(artifact, artifactPolicy(env, requireFullMemory));

if (artifactOutputPath !== undefined && artifactOutputPath.trim().length > 0) {
  await writeJsonFile(artifactOutputPath, artifact);
}

const primaryPayload = outputMode === "artifact" ? artifact : report;
const serialized = `${JSON.stringify(primaryPayload, null, 2)}\n`;
if (outputPath === undefined || outputPath.trim().length === 0) {
  process.stdout.write(serialized);
} else {
  const resolvedOutputPath = await writeJsonFile(outputPath, primaryPayload);
  process.stdout.write(`${resolvedOutputPath}\n`);
}

if (!artifactEvaluation.ok) {
  process.stderr.write(`Full memory proof artifact policy failed: ${artifactEvaluation.errors.join("; ")}\n`);
}

if (!report.ok || !artifactEvaluation.ok) {
  process.exitCode = 1;
}

function parsePositiveInteger(value) {
  if (value === undefined) {
    return undefined;
  }
  const parsed = Number(value);

  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
}

function parseNonNegativeInteger(value) {
  if (value === undefined) {
    return undefined;
  }
  const parsed = Number(value);

  return Number.isInteger(parsed) && parsed >= 0 ? parsed : undefined;
}

function parseNonNegativeNumber(value) {
  if (value === undefined) {
    return undefined;
  }
  const parsed = Number(value);

  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
}

function parseBoolean(value, fallback) {
  if (value === undefined) {
    return fallback;
  }
  return !["0", "false", "no"].includes(value.toLowerCase());
}

async function writeJsonFile(path, payload) {
  const resolvedOutputPath = resolve(path);
  await mkdir(dirname(resolvedOutputPath), { recursive: true });
  await writeFile(resolvedOutputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  return resolvedOutputPath;
}

async function readPackageMetadata() {
  try {
    const text = await readFile(new URL("../package.json", import.meta.url), "utf8");
    const parsed = JSON.parse(text);
    return {
      ...(typeof parsed.name === "string" ? { packageName: parsed.name } : {}),
      ...(typeof parsed.version === "string" ? { packageVersion: parsed.version } : {}),
    };
  } catch {
    return {};
  }
}

function gitMetadata(env) {
  return {
    ...firstString(env, "commitSha", [
      "GITHUB_SHA",
      "VERCEL_GIT_COMMIT_SHA",
      "COMMIT_SHA",
      "GIT_COMMIT",
      "CI_COMMIT_SHA",
      "BUILD_SOURCEVERSION",
    ]),
    ...firstString(env, "branch", [
      "GITHUB_REF_NAME",
      "VERCEL_GIT_COMMIT_REF",
      "BRANCH_NAME",
      "CI_COMMIT_BRANCH",
      "BUILD_SOURCEBRANCHNAME",
    ]),
    ...firstString(env, "repository", [
      "GITHUB_REPOSITORY",
      "VERCEL_GIT_REPO_SLUG",
      "CI_PROJECT_PATH",
      "BUILD_REPOSITORY_NAME",
    ]),
  };
}

function firstString(env, outputKey, keys) {
  const value = keys
    .map((key) => env[key])
    .find((item) => typeof item === "string" && item.trim().length > 0);

  return value === undefined ? {} : { [outputKey]: value };
}

function artifactPolicy(env, requireFullMemory) {
  return {
    requireOk: true,
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
    requireGitCommit: parseBoolean(env.INFINITY_CONTEXT_PROOF_REQUIRE_GIT_COMMIT, false),
    requirePackageVersion: parseBoolean(env.INFINITY_CONTEXT_PROOF_REQUIRE_PACKAGE_VERSION, false),
  };
}

function numberPolicy(outputKey, value, parse) {
  const parsed = parse(value);

  return parsed === undefined ? {} : { [outputKey]: parsed };
}

function csvPolicy(outputKey, value) {
  if (value === undefined) {
    return {};
  }
  const items = value.split(",").map((item) => item.trim()).filter(Boolean);

  return items.length === 0 ? {} : { [outputKey]: items };
}

function parseUnitInterval(value) {
  const parsed = parseNonNegativeNumber(value);

  return parsed !== undefined && parsed <= 1 ? parsed : undefined;
}
