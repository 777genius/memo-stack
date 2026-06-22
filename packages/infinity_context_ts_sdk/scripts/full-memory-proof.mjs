#!/usr/bin/env node
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import { InfinityContextClient, runFullMemoryProof } from "../dist/index.js";

const env = process.env;
const baseUrl = env.INFINITY_CONTEXT_URL ?? "http://127.0.0.1:7788";
const token = env.INFINITY_CONTEXT_TOKEN;
const outputPath = env.INFINITY_CONTEXT_PROOF_OUTPUT;
const requireFullMemory = env.INFINITY_CONTEXT_PROOF_REQUIRE_FULL_MEMORY === undefined
  ? true
  : !["0", "false", "no"].includes(env.INFINITY_CONTEXT_PROOF_REQUIRE_FULL_MEMORY.toLowerCase());

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

const serialized = `${JSON.stringify(report, null, 2)}\n`;
if (outputPath === undefined || outputPath.trim().length === 0) {
  process.stdout.write(serialized);
} else {
  const resolvedOutputPath = resolve(outputPath);
  await mkdir(dirname(resolvedOutputPath), { recursive: true });
  await writeFile(resolvedOutputPath, serialized, "utf8");
  process.stdout.write(`${resolvedOutputPath}\n`);
}

if (!report.ok) {
  process.exitCode = 1;
}

function parsePositiveInteger(value) {
  if (value === undefined) {
    return undefined;
  }
  const parsed = Number(value);

  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
}
