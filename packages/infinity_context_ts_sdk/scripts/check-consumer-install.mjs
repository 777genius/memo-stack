#!/usr/bin/env node
import { execFile } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const packageRoot = fileURLToPath(new URL("..", import.meta.url));
const tscPath = fileURLToPath(new URL("../node_modules/typescript/bin/tsc", import.meta.url));

const tempRoot = await mkdtemp(join(tmpdir(), "infinity-context-sdk-consumer-"));

try {
  const pack = await execFileAsync("npm", ["pack", "--json", "--pack-destination", tempRoot], {
    cwd: packageRoot,
    maxBuffer: 10 * 1024 * 1024,
  });
  const [packResult] = JSON.parse(pack.stdout);
  if (packResult === undefined || typeof packResult.filename !== "string") {
    throw new Error("npm pack did not return a package filename");
  }

  await writeFile(join(tempRoot, "package.json"), JSON.stringify({ private: true }, null, 2));
  await execFileAsync("npm", ["install", "--ignore-scripts", "--no-audit", "--no-fund", `./${packResult.filename}`], {
    cwd: tempRoot,
    maxBuffer: 10 * 1024 * 1024,
  });

  await writeFile(join(tempRoot, "consumer.ts"), consumerTypecheckSource());
  await writeFile(join(tempRoot, "consumer-esm.mjs"), consumerEsmSource());
  await writeFile(join(tempRoot, "consumer-cjs.cjs"), consumerCjsSource());
  await writeFile(join(tempRoot, "tsconfig.json"), JSON.stringify({
    compilerOptions: {
      target: "ES2022",
      lib: ["ES2022", "DOM"],
      module: "NodeNext",
      moduleResolution: "NodeNext",
      strict: true,
      exactOptionalPropertyTypes: true,
      noUncheckedIndexedAccess: true,
      skipLibCheck: false,
      noEmit: true,
    },
    include: ["consumer.ts"],
  }, null, 2));

  await execFileAsync(process.execPath, [tscPath, "-p", join(tempRoot, "tsconfig.json")], {
    cwd: tempRoot,
    maxBuffer: 10 * 1024 * 1024,
  });
  await execFileAsync(process.execPath, [join(tempRoot, "consumer-esm.mjs")], {
    cwd: tempRoot,
    maxBuffer: 10 * 1024 * 1024,
  });
  await execFileAsync(process.execPath, [join(tempRoot, "consumer-cjs.cjs")], {
    cwd: tempRoot,
    maxBuffer: 10 * 1024 * 1024,
  });

  console.log(`Consumer install ok: ${packResult.filename}`);
} finally {
  await rm(tempRoot, { force: true, recursive: true });
}

function consumerTypecheckSource() {
  return `import {
  InfinityContextClient,
  ReadScope,
  assertMemoryBriefQuality,
  createMemoryReviewPlan,
  createMemorySummaryLoopPlan,
  type ApplyMemoryReviewPlanResult,
  type BuildMemoryBriefInput,
  type MemoryReviewPlan,
} from "@infinity-context/sdk";
import { noopInstrumentation } from "@infinity-context/sdk/instrumentation";
import { iterateCursorItems } from "@infinity-context/sdk/pagination";
import { runRuntimeCanary } from "@infinity-context/sdk/canary";
import { runFullMemoryProof } from "@infinity-context/sdk/proof";
import { assertFullMemoryReady } from "@infinity-context/sdk/runtime";
import {
  MemoryWorkflows,
  createMemoryScopePlan,
  type ApplyMemoryReviewPlanSummary,
} from "@infinity-context/sdk/workflows";

const client = new InfinityContextClient({
  baseUrl: "http://127.0.0.1:7788",
  token: "test-token",
  instrumentation: noopInstrumentation(),
});

const reviewPlan: MemoryReviewPlan = createMemoryReviewPlan({
  reason: "consumer smoke",
  contextLinks: {
    items: [{ suggestionId: "ctx_suggestion_1", action: "reject" }],
  },
  suggestions: {
    items: [{ suggestionId: "memory_suggestion_1", action: "approve" }],
  },
});

const applied: Promise<ApplyMemoryReviewPlanResult> = client.workflows.applyMemoryReviewPlan(reviewPlan);
const readScope = ReadScope.external({
  spaceSlug: "workspace",
  memoryScopeExternalRefs: ["scope"],
});
const brief: BuildMemoryBriefInput = {
  query: "What should the digest prioritize?",
  readScope,
};
const summaryLoop = createMemorySummaryLoopPlan({ brief });
const scopePlan = createMemoryScopePlan({
  spaceSlug: "workspace",
  topics: [{ slug: "scope", name: "Scope" }],
});
const workflowCtor: typeof MemoryWorkflows = MemoryWorkflows;
const appliedSummary: ApplyMemoryReviewPlanSummary = {
  total: 2,
  contextLinkReviews: 1,
  suggestionReviews: 1,
  byAction: { approve: 1, reject: 1 },
  applied: 2,
  failed: 0,
  stopped: false,
};

void applied;
void brief;
void summaryLoop;
void scopePlan;
void workflowCtor;
void appliedSummary;
void assertMemoryBriefQuality;
void assertFullMemoryReady;
void iterateCursorItems;
void runRuntimeCanary;
void runFullMemoryProof;
`;
}

function consumerEsmSource() {
  return `import { InfinityContextClient, createMemoryReviewPlan } from "@infinity-context/sdk";
import { MemoryWorkflows } from "@infinity-context/sdk/workflows";
import { noopInstrumentation } from "@infinity-context/sdk/instrumentation";
import { assertFullMemoryReady } from "@infinity-context/sdk/runtime";
import { runRuntimeCanary } from "@infinity-context/sdk/canary";
import { runFullMemoryProof } from "@infinity-context/sdk/proof";
import { iterateCursorItems } from "@infinity-context/sdk/pagination";

for (const value of [
  InfinityContextClient,
  createMemoryReviewPlan,
  MemoryWorkflows,
  noopInstrumentation,
  assertFullMemoryReady,
  runRuntimeCanary,
  runFullMemoryProof,
  iterateCursorItems,
]) {
  if (value === undefined) {
    throw new Error("Missing ESM consumer export");
  }
}
`;
}

function consumerCjsSource() {
  return `const { InfinityContextClient, createMemoryReviewPlan } = require("@infinity-context/sdk");
const { MemoryWorkflows } = require("@infinity-context/sdk/workflows");
const { noopInstrumentation } = require("@infinity-context/sdk/instrumentation");
const { assertFullMemoryReady } = require("@infinity-context/sdk/runtime");
const { runRuntimeCanary } = require("@infinity-context/sdk/canary");
const { runFullMemoryProof } = require("@infinity-context/sdk/proof");
const { iterateCursorItems } = require("@infinity-context/sdk/pagination");

for (const value of [
  InfinityContextClient,
  createMemoryReviewPlan,
  MemoryWorkflows,
  noopInstrumentation,
  assertFullMemoryReady,
  runRuntimeCanary,
  runFullMemoryProof,
  iterateCursorItems,
]) {
  if (value === undefined) {
    throw new Error("Missing CJS consumer export");
  }
}
`;
}
