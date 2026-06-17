#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");

const args = process.argv.slice(2);
const command = args[0];
const vault = process.env.MEMO_STACK_OBSIDIAN_VAULT || process.cwd();

const memoDir = path.join(vault, ".memo-stack");
fs.mkdirSync(memoDir, { recursive: true });

delayFromEnv("MEMO_STACK_FAKE_LOCAL_DELAY_MS");
if (process.env.MEMO_STACK_FAKE_LOCAL_FAIL_COMMAND === command) {
  fail(process.env.MEMO_STACK_FAKE_LOCAL_FAIL_MESSAGE || `Forced fake local stack failure: ${command}`);
}

if (command === "status") {
  const ready = process.env.MEMO_STACK_FAKE_LOCAL_STATUS_READY !== "false";
  emit({
    ok: true,
    api_url: process.env.MEMORY_API_URL || "http://127.0.0.1:7788",
    health: { status_code: ready ? 200 : 503, data: { ok: ready } },
    capabilities: { status_code: ready ? 200 : 503, data: { ok: ready } },
  });
}

if (command === "init") {
  emit({
    ok: true,
    home: path.join(vault, ".memo-stack-home"),
    repo_dir: process.cwd(),
    api_url: valueAfter("--api-url") || "http://127.0.0.1:7788",
    token_configured: true,
  });
}

if (command === "doctor") {
  emit({
    ok: true,
    checks: [
      { name: "repo_root", ok: true, message: "repo root resolved" },
      { name: "docker", ok: true, message: "docker command available" },
    ],
  });
}

if (command === "up" && args.includes("--lite")) {
  recordCall(0);
  process.stdout.write("local stack started\n");
  process.exit(0);
}

fail(`Unknown fake memo-stack command: ${args.join(" ")}`);

function emit(payload) {
  recordCall(0);
  process.stdout.write(`${JSON.stringify(payload)}\n`);
  process.exit(0);
}

function valueAfter(flag) {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : "";
}

function fail(message) {
  recordCall(1);
  process.stderr.write(`${message}\n`);
  process.exit(1);
}

function recordCall(status) {
  fs.appendFileSync(
    path.join(memoDir, "local-stack-calls.jsonl"),
    JSON.stringify({
      command,
      args,
      apiUrl: process.env.MEMORY_API_URL || "",
      envToken: process.env.MEMORY_SERVICE_TOKEN || "",
      status,
    }) + "\n",
  );
}

function delayFromEnv(name) {
  const ms = Number.parseInt(process.env[name] || "0", 10);
  if (Number.isFinite(ms) && ms > 0) {
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
  }
}
