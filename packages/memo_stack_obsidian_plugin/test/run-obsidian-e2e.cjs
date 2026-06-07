#!/usr/bin/env node

const { spawnSync } = require("node:child_process");

if (process.env.MEMO_STACK_RUN_OBSIDIAN_E2E !== "1") {
  console.log(
    [
      "Skipping Obsidian UI E2E.",
      "This test launches the real Obsidian desktop app and may take focus.",
      "Run explicitly with:",
      "  MEMO_STACK_RUN_OBSIDIAN_E2E=1 npm run test:e2e:obsidian",
    ].join("\n"),
  );
  process.exit(0);
}

const npm = process.platform === "win32" ? "npm.cmd" : "npm";
const result = spawnSync(npm, ["run", "test:e2e:obsidian:run"], {
  stdio: "inherit",
  env: process.env,
});
process.exit(result.status ?? 1);
