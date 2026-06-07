#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const repoRoot = path.resolve(__dirname, "../../../..");
const python = process.env.MEMO_STACK_E2E_PYTHON || path.join(repoRoot, ".venv/bin/python");
const args = process.argv.slice(2);
const vault = valueAfter("--vault");

const env = { ...process.env };
env.PYTHONPATH = pythonpath(repoRoot, env.PYTHONPATH);

delayFromEnv("MEMO_STACK_REAL_OBSIDIAN_DELAY_MS");

const result = spawnSync(python, ["-m", "memo_stack_obsidian.cli", ...args], {
  cwd: repoRoot,
  env,
  encoding: "utf8",
  maxBuffer: 1024 * 1024,
});

if (vault) {
  const memoDir = path.join(vault, ".memo-stack");
  fs.mkdirSync(memoDir, { recursive: true });
  fs.appendFileSync(
    path.join(memoDir, "real-plugin-cli-calls.jsonl"),
    JSON.stringify({ command: args[0] || "", args, status: result.status ?? 1 }) + "\n",
  );
}

if (result.stdout) {
  process.stdout.write(result.stdout);
}
if (result.stderr) {
  process.stderr.write(result.stderr);
}
process.exit(result.status ?? 1);

function valueAfter(flag) {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : "";
}

function pythonpath(root, existing) {
  const values = [
    "packages/memo_stack_core",
    "packages/memo_stack_adapters",
    "packages/memo_stack_server",
    "packages/memo_stack_sdk",
    "packages/memo_stack_obsidian",
  ].map((relativePath) => path.join(root, relativePath));
  if (existing) {
    values.push(existing);
  }
  return values.join(path.delimiter);
}

function delayFromEnv(name) {
  const ms = Number.parseInt(process.env[name] || "0", 10);
  if (Number.isFinite(ms) && ms > 0) {
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
  }
}
