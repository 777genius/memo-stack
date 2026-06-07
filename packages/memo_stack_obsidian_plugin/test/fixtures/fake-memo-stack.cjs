#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");

const args = process.argv.slice(2);
const command = args[0];
const vault = process.env.MEMO_STACK_OBSIDIAN_VAULT || process.cwd();

const memoDir = path.join(vault, ".memo-stack");
fs.mkdirSync(memoDir, { recursive: true });
fs.appendFileSync(
  path.join(memoDir, "local-stack-calls.jsonl"),
  JSON.stringify({
    command,
    args,
    apiUrl: process.env.MEMORY_API_URL || "",
    envToken: process.env.MEMORY_SERVICE_TOKEN || "",
  }) + "\n",
);

if (command === "status") {
  emit({
    ok: true,
    api_url: process.env.MEMORY_API_URL || "http://127.0.0.1:7788",
    health: { status_code: 200, data: { ok: true } },
    capabilities: { status_code: 200, data: { ok: true } },
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
  process.stdout.write("local stack started\n");
  process.exit(0);
}

process.stderr.write(`Unknown fake memo-stack command: ${args.join(" ")}\n`);
process.exit(1);

function emit(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
  process.exit(0);
}

function valueAfter(flag) {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : "";
}
