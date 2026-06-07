#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");

const args = process.argv.slice(2);
const command = args[0];
const vault = valueAfter("--vault");
if (!command || !vault) {
  fail("Usage: fake-memo-stack-obsidian <command> --vault <path>");
}

const memoDir = path.join(vault, ".memo-stack");
const layout = layoutPaths();
fs.mkdirSync(memoDir, { recursive: true });
fs.appendFileSync(
  path.join(memoDir, "plugin-cli-calls.jsonl"),
  JSON.stringify({ command, args, envToken: process.env.MEMORY_SERVICE_TOKEN || "" }) + "\n",
);

if (command === "connect") {
  write(layout.readme, "# Memo Stack\n\nConnected by plugin E2E.\n");
  write(path.join(layout.inbox, "README.md"), "# Inbox\n");
  write(path.join(layout.conflicts, "README.md"), "# Conflicts\n");
  write(path.join(layout.generatedFacts, ".gitkeep.md"), "# Generated Facts\n");
  emit({
    ok: true,
    written: [layout.readme],
    skipped: [],
    next: "Run preview.",
  });
}

if (command === "doctor") {
  emit({
    ok: true,
    checks: [
      { name: "vault_exists", ok: true, required: true, message: "Vault exists" },
      { name: "generated_facts_dir", ok: true, required: true, message: layout.generatedFacts },
      { name: "backend_health", ok: true, required: true, message: "Backend is reachable" },
    ],
  });
}

if (command === "preview") {
  emit({
    ok: true,
    export: { would_export: 1, skipped: 0, conflicts: 0, changes: [] },
    import: { would_update: 0, would_suggest: 0, conflicts: 0, changes: [] },
  });
}

if (command === "sync") {
  write(
    path.join(layout.generatedFacts, "plugin-e2e.md"),
    [
      "---",
      "memo_stack_schema: memo_stack.obsidian.fact.v1",
      "memo_stack_kind: fact",
      "memo_stack_id: plugin-e2e",
      "memo_stack_version: 1",
      "memo_stack_sync_mode: direct",
      "memo_stack_managed: true",
      "---",
      "# Plugin E2E fact",
      "",
      "<!-- memo-stack-managed:fact-text:start -->",
      "Plugin E2E fact",
      "<!-- memo-stack-managed:fact-text:end -->",
      "",
    ].join("\n"),
  );
  emit({
    ok: true,
    applied_import: args.includes("--apply-import"),
    export_skipped: false,
    export_skipped_reason: "",
    import: {
      ok: true,
      applied: args.includes("--apply-import"),
      updated: 0,
      would_update: 0,
      suggested: 0,
      would_suggest: 0,
      conflicts: 0,
      changes: [],
    },
    export: {
      exported: 1,
      skipped: 0,
      conflicts: 0,
      conflict_artifacts_written: 0,
      paths: [path.join(layout.generatedFacts, "plugin-e2e.md")],
      conflict_artifacts: [],
      changes: [],
    },
  });
}

fail(`Unknown command: ${command}`);

function valueAfter(flag) {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : "";
}

function write(relativePath, content) {
  const absolute = path.join(vault, relativePath);
  fs.mkdirSync(path.dirname(absolute), { recursive: true });
  fs.writeFileSync(absolute, content, "utf8");
}

function layoutPaths() {
  const root = valueAfter("--root-folder") || "Memo Stack";
  if ((valueAfter("--layout") || "v2") === "v1") {
    return {
      readme: path.join(root, "README.md"),
      generatedFacts: path.join(root, "generated", "facts"),
      inbox: path.join(root, "inbox"),
      conflicts: path.join(root, "conflicts"),
    };
  }
  const space = valueAfter("--space") || "default";
  const profile = valueAfter("--profile") || "default";
  const scope = path.join(root, "spaces", space, "profiles", profile);
  return {
    readme: path.join(root, "README.md"),
    generatedFacts: path.join(scope, "generated", "facts"),
    inbox: path.join(scope, "inbox"),
    conflicts: path.join(scope, "conflicts"),
  };
}

function emit(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
  process.exit(0);
}

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}
