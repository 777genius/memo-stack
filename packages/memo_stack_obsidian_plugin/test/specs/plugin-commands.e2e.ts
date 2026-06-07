import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { browser } from "@wdio/globals";

const fakeCliPath = path.resolve("test/fixtures/fake-memo-stack-obsidian.cjs");
const fakeLocalCliPath = path.resolve("test/fixtures/fake-memo-stack.cjs");
const spaceSlug = "wdio-e2e";
const profileExternalRef = "default";
const factsDir = path.join(
  "Memo Stack",
  "spaces",
  spaceSlug,
  "profiles",
  profileExternalRef,
  "generated",
  "facts",
);

describe("Memo Stack Obsidian plugin", function () {
  it("registers commands and delegates sync actions to the connector CLI", async function () {
    const obsidianPage = await browser.getObsidianPage();
    const vaultPath = obsidianPage.getVaultPath();

    await browser.executeObsidian(
      async ({ plugins }, settings) => {
        const plugin = plugins.memoStack as any;
        Object.assign(plugin.settings, settings);
        await plugin.saveSettings();
      },
      {
        apiUrl: "http://127.0.0.1:65535",
        token: "wdio-token",
        localCliPath: fakeLocalCliPath,
        cliPath: fakeCliPath,
        vaultPathOverride: vaultPath,
        spaceSlug,
        profileExternalRef,
        rootFolder: "Memo Stack",
        layoutVersion: "v2",
        applyImportOnSync: true,
        commandTimeoutMs: 10000,
      },
    );

    const commandIds = await browser.executeObsidian(({ app }) => {
      return Object.keys((app as any).commands.commands)
        .filter((id) => id.startsWith("memo-stack:"))
        .sort();
    });
    assert.deepEqual(commandIds, [
      "memo-stack:check-daemon-health",
      "memo-stack:connect-vault",
      "memo-stack:local-stack-doctor",
      "memo-stack:local-stack-init",
      "memo-stack:local-stack-status",
      "memo-stack:open-conflicts",
      "memo-stack:open-control-center",
      "memo-stack:open-inbox",
      "memo-stack:open-memo-stack-readme",
      "memo-stack:prepare-vault",
      "memo-stack:preview-sync",
      "memo-stack:run-doctor",
      "memo-stack:start-local-stack-lite",
      "memo-stack:sync-now",
    ]);

    await browser.executeObsidianCommand("memo-stack:open-control-center");
    const panelOpened = await browser.executeObsidian(({ app }) => {
      return app.workspace.getLeavesOfType("memo-stack-control-center").length === 1;
    });
    assert.equal(panelOpened, true);
    assert.equal(readCliCalls(vaultPath).length, 0);
    assert.equal(readLocalStackCalls(vaultPath).length, 0);

    await browser.executeObsidianCommand("memo-stack:prepare-vault");
    await waitForLocalStackCalls(vaultPath, 2);
    await waitForCliCalls(vaultPath, 2);
    assert.deepEqual(
      readLocalStackCalls(vaultPath).map((call) => call.args.join(" ")),
      ["init --api-url http://127.0.0.1:65535 --json", "status --json"],
    );
    assert.deepEqual(
      readCliCalls(vaultPath).map((call) => call.command),
      ["connect", "preview"],
    );

    await browser.executeObsidianCommand("memo-stack:local-stack-init");
    await waitForLocalStackCalls(vaultPath, 3);
    await browser.executeObsidianCommand("memo-stack:local-stack-status");
    await waitForLocalStackCalls(vaultPath, 4);
    await browser.executeObsidianCommand("memo-stack:start-local-stack-lite");
    await waitForLocalStackCalls(vaultPath, 5);
    await browser.executeObsidianCommand("memo-stack:start-local-stack-lite");
    await browser.pause(300);
    assert.equal(readLocalStackCalls(vaultPath).length, 5);

    await browser.executeObsidianCommand("memo-stack:connect-vault");
    await waitForCliCalls(vaultPath, 3);
    const readme = readVaultFile(vaultPath, "Memo Stack/README.md");
    assert.match(readme, /Connected by plugin E2E/);

    await browser.executeObsidianCommand("memo-stack:run-doctor");
    await waitForCliCalls(vaultPath, 4);
    await browser.executeObsidianCommand("memo-stack:preview-sync");
    await waitForCliCalls(vaultPath, 5);
    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 6);
    const fact = readVaultFile(vaultPath, path.join(factsDir, "plugin-e2e.md"));
    assert.match(fact, /Plugin E2E fact/);

    await browser.executeObsidianCommand("memo-stack:open-memo-stack-readme");
    const activeFilePath = await browser.executeObsidian(({ app }) => {
      return app.workspace.getActiveFile()?.path ?? "";
    });
    assert.equal(activeFilePath, "Memo Stack/README.md");

    await browser.executeObsidianCommand("memo-stack:open-conflicts");
    const activeConflictPath = await browser.executeObsidian(({ app }) => {
      return app.workspace.getActiveFile()?.path ?? "";
    });
    assert.equal(
      activeConflictPath,
      ["Memo Stack", "spaces", spaceSlug, "profiles", profileExternalRef, "conflicts", "README.md"].join("/"),
    );

    const calls = readCliCalls(vaultPath);
    assert.deepEqual(
      calls.map((call) => call.command),
      ["connect", "preview", "connect", "doctor", "preview", "sync"],
    );
    assert.equal(calls[0].envToken, "wdio-token");
    assert.ok(calls[5].args.includes("--apply-import"));
    assert.ok(calls.every((call) => call.args.includes("--json")));
    assert.ok(calls.every((call) => call.args.includes("--space")));
    assert.ok(calls.every((call) => call.args.includes(spaceSlug)));
    assert.ok(calls.every((call) => call.args.includes("--root-folder")));
    assert.ok(calls.every((call) => call.args.includes("--layout")));

    const stackCalls = readLocalStackCalls(vaultPath);
    assert.deepEqual(
      stackCalls.map((call) => call.args.join(" ")),
      [
        "init --api-url http://127.0.0.1:65535 --json",
        "status --json",
        "init --api-url http://127.0.0.1:65535 --json",
        "status --json",
        "up --lite",
      ],
    );
    assert.equal(stackCalls[0].envToken, "wdio-token");
    assert.equal(stackCalls[0].apiUrl, "http://127.0.0.1:65535");
  });
});

async function waitForCliCalls(vaultPath: string, count: number): Promise<void> {
  await browser.waitUntil(() => readCliCalls(vaultPath).length >= count, {
    timeout: 10000,
    timeoutMsg: `Expected ${count} connector CLI calls`,
  });
}

async function waitForLocalStackCalls(vaultPath: string, count: number): Promise<void> {
  await browser.waitUntil(() => readLocalStackCalls(vaultPath).length >= count, {
    timeout: 10000,
    timeoutMsg: `Expected ${count} local stack CLI calls`,
  });
}

function readCliCalls(vaultPath: string): Array<{
  command: string;
  args: string[];
  envToken: string;
}> {
  const logPath = path.join(vaultPath, ".memo-stack/plugin-cli-calls.jsonl");
  if (!fs.existsSync(logPath)) {
    return [];
  }
  return fs
    .readFileSync(logPath, "utf8")
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function readLocalStackCalls(vaultPath: string): Array<{
  command: string;
  args: string[];
  apiUrl: string;
  envToken: string;
}> {
  const logPath = path.join(vaultPath, ".memo-stack/local-stack-calls.jsonl");
  if (!fs.existsSync(logPath)) {
    return [];
  }
  return fs
    .readFileSync(logPath, "utf8")
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function readVaultFile(vaultPath: string, relativePath: string): string {
  return fs.readFileSync(path.join(vaultPath, relativePath), "utf8");
}
