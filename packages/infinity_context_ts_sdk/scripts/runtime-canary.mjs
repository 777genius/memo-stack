#!/usr/bin/env node
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

const env = process.env;
const baseUrl = env.INFINITY_CONTEXT_URL ?? "http://127.0.0.1:7788";
const token = env.INFINITY_CONTEXT_TOKEN;
const outputPath = env.INFINITY_CONTEXT_CANARY_OUTPUT;
const requireReady = env.INFINITY_CONTEXT_CANARY_REQUIRE_READY === undefined
  ? true
  : !["0", "false", "no"].includes(env.INFINITY_CONTEXT_CANARY_REQUIRE_READY.toLowerCase());
const shouldWait = parseBoolean(env.INFINITY_CONTEXT_CANARY_WAIT, false);
const packageMetadata = await readPackageMetadata();
const commandName = "infinity-context-runtime-canary";
const cliArgs = process.argv.slice(2);

if (hasCliFlag(cliArgs, "--help", "-h")) {
  printRuntimeCanaryHelp(commandName);
  process.exit(0);
}

if (hasCliFlag(cliArgs, "--version", "-v")) {
  process.stdout.write(`${packageMetadata.packageVersion ?? "0.0.0"}\n`);
  process.exit(0);
}

const { InfinityContextClient, runRuntimeCanary, waitForRuntimeCanary } = await import("../dist/index.js");

const canaryOptions = {
  client: new InfinityContextClient({
    baseUrl,
    token: () => token,
    timeoutMs: parsePositiveInteger(env.INFINITY_CONTEXT_CANARY_TIMEOUT_MS) ?? 15_000,
    retryPolicy: { maxAttempts: 2 },
  }),
  ...(env.INFINITY_CONTEXT_CANARY_QUERY !== undefined ? { query: env.INFINITY_CONTEXT_CANARY_QUERY } : {}),
  ...(env.INFINITY_CONTEXT_CANARY_SPACE_SLUG !== undefined ? { spaceSlug: env.INFINITY_CONTEXT_CANARY_SPACE_SLUG } : {}),
  ...externalRefs("INFINITY_CONTEXT_CANARY_MEMORY_SCOPE_EXTERNAL_REFS"),
  ...canonicalIds("INFINITY_CONTEXT_CANARY_MEMORY_SCOPE_IDS"),
  ...(env.INFINITY_CONTEXT_CANARY_THREAD_EXTERNAL_REF !== undefined
    ? { threadExternalRef: env.INFINITY_CONTEXT_CANARY_THREAD_EXTERNAL_REF }
    : {}),
  includeContextProbe: parseBoolean(env.INFINITY_CONTEXT_CANARY_INCLUDE_CONTEXT_PROBE, true),
  includeSearchProbe: parseBoolean(env.INFINITY_CONTEXT_CANARY_INCLUDE_SEARCH_PROBE, false),
  requireDerivedRetrieval: parseBoolean(env.INFINITY_CONTEXT_CANARY_REQUIRE_DERIVED_RETRIEVAL, true),
  tokenBudget: parsePositiveInteger(env.INFINITY_CONTEXT_CANARY_TOKEN_BUDGET),
  maxFacts: parsePositiveInteger(env.INFINITY_CONTEXT_CANARY_MAX_FACTS),
  maxChunks: parsePositiveInteger(env.INFINITY_CONTEXT_CANARY_MAX_CHUNKS),
  maxEvidenceItems: parsePositiveInteger(env.INFINITY_CONTEXT_CANARY_MAX_EVIDENCE_ITEMS),
  ...(env.INFINITY_CONTEXT_CANARY_CONSISTENCY_MODE !== undefined
    ? { consistencyMode: env.INFINITY_CONTEXT_CANARY_CONSISTENCY_MODE }
    : {}),
  maxAttempts: parsePositiveInteger(env.INFINITY_CONTEXT_CANARY_MAX_ATTEMPTS),
  pollIntervalMs: parseNonNegativeNumber(env.INFINITY_CONTEXT_CANARY_POLL_INTERVAL_MS),
};
const report = shouldWait
  ? await waitForRuntimeCanary(canaryOptions)
  : await runRuntimeCanary(canaryOptions);

const serialized = `${JSON.stringify(report, null, 2)}\n`;
if (outputPath === undefined || outputPath.trim().length === 0) {
  process.stdout.write(serialized);
} else {
  const resolvedOutputPath = resolve(outputPath);
  await mkdir(dirname(resolvedOutputPath), { recursive: true });
  await writeFile(resolvedOutputPath, serialized, "utf8");
  process.stdout.write(`${resolvedOutputPath}\n`);
}

if (requireReady && !report.ok) {
  process.exitCode = 1;
}

function hasCliFlag(args, ...flags) {
  return args.some((arg) => flags.includes(arg));
}

function printRuntimeCanaryHelp(command) {
  process.stdout.write(`Usage: ${command} [--help] [--version]

Runs a non-mutating runtime canary against an Infinity Context service.

Options:
  -h, --help       Show this help without contacting the service.
  -v, --version    Print the package version.

Environment:
  INFINITY_CONTEXT_URL                                Service base URL. Default: http://127.0.0.1:7788
  INFINITY_CONTEXT_TOKEN                              Bearer token for the service.
  INFINITY_CONTEXT_CANARY_OUTPUT                      Optional report output JSON path.
  INFINITY_CONTEXT_CANARY_WAIT                        Poll until ready instead of one probe. Default: false.
  INFINITY_CONTEXT_CANARY_REQUIRE_READY               Exit non-zero when runtime is not ready. Default: true.
  INFINITY_CONTEXT_CANARY_SPACE_SLUG                  Optional memory space slug.
  INFINITY_CONTEXT_CANARY_MEMORY_SCOPE_EXTERNAL_REFS  Optional comma-separated memory scope refs.
  INFINITY_CONTEXT_CANARY_INCLUDE_SEARCH_PROBE        Include search probe. Default: false.
  INFINITY_CONTEXT_CANARY_TIMEOUT_MS                  Per-request timeout. Default: 15000.
`);
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

function parsePositiveInteger(value) {
  if (value === undefined) {
    return undefined;
  }
  const parsed = Number(value);

  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
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

function splitCsv(value) {
  if (value === undefined) {
    return undefined;
  }
  const items = value.split(",").map((item) => item.trim()).filter(Boolean);
  return items.length === 0 ? undefined : items;
}

function externalRefs(envKey) {
  const values = splitCsv(env[envKey]);
  return values === undefined ? {} : { memoryScopeExternalRefs: values };
}

function canonicalIds(envKey) {
  const values = splitCsv(env[envKey]);
  return values === undefined ? {} : { memoryScopeIds: values };
}
