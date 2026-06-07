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
const fakeEnvKeys = [
  "MEMO_STACK_FAKE_OBSIDIAN_DELAY_MS",
  "MEMO_STACK_FAKE_OBSIDIAN_FAIL_COMMAND",
  "MEMO_STACK_FAKE_LOCAL_DELAY_MS",
  "MEMO_STACK_FAKE_LOCAL_FAIL_COMMAND",
  "MEMO_STACK_FAKE_LOCAL_STATUS_READY",
];

describe("Memo Stack Obsidian plugin", function () {
  beforeEach(async function () {
    await clearFakeEnv();
  });

  afterEach(async function () {
    await clearFakeEnv();
  });

  it("registers commands and delegates sync actions to the connector CLI", async function () {
    const vaultPath = await resetVaultAndConfigure();

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
    assert.ok(calls.every((call) => call.status === 0));
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
    assert.ok(stackCalls.every((call) => call.status === 0));
  });

  it("blocks overlapping connector commands while the first command is still running", async function () {
    const vaultPath = await resetVaultAndConfigure({ commandTimeoutMs: 5000 });
    await setFakeEnv({ MEMO_STACK_FAKE_OBSIDIAN_DELAY_MS: "1200" });

    const snapshots = await browser.executeObsidian(async ({ plugins }) => {
      const plugin = plugins.memoStack as any;
      void plugin.syncNow();
      await new Promise((resolve) => setTimeout(resolve, 100));
      const duringFirst = plugin.snapshot();
      await plugin.syncNow();
      const afterSecond = plugin.snapshot();
      return { duringFirst, afterSecond };
    });

    assert.equal(snapshots.duringFirst.busyLabel, "syncing vault");
    assert.equal(snapshots.afterSecond.busyLabel, "syncing vault");
    await waitForCliCalls(vaultPath, 1);
    await waitForPluginIdle();
    await browser.pause(150);

    const calls = readCliCalls(vaultPath);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].command, "sync");
    assert.equal(calls[0].status, 0);
  });

  it("surfaces connector failures and clears busy state", async function () {
    const vaultPath = await resetVaultAndConfigure();
    await setFakeEnv({ MEMO_STACK_FAKE_OBSIDIAN_FAIL_COMMAND: "preview" });

    await browser.executeObsidianCommand("memo-stack:preview-sync");
    await waitForCliCalls(vaultPath, 1);
    const snapshot = await memoStackSnapshot();
    const calls = readCliCalls(vaultPath);

    assert.equal(calls[0].command, "preview");
    assert.equal(calls[0].status, 1);
    assert.equal(snapshot.busyLabel, "");
    assert.equal(snapshot.lastCommand, "preview");
    assert.equal(snapshot.lastResult.exitCode, 1);
    assert.match(snapshot.lastResult.stderr, /Forced fake connector failure/);
  });

  it("stops prepare before vault writes when local init fails", async function () {
    const vaultPath = await resetVaultAndConfigure();
    await setFakeEnv({ MEMO_STACK_FAKE_LOCAL_FAIL_COMMAND: "init" });

    await browser.executeObsidianCommand("memo-stack:prepare-vault");
    await waitForLocalStackCalls(vaultPath, 1);
    await browser.pause(150);
    const snapshot = await memoStackSnapshot();

    assert.deepEqual(
      readLocalStackCalls(vaultPath).map((call) => `${call.command}:${call.status}`),
      ["init:1"],
    );
    assert.equal(readCliCalls(vaultPath).length, 0);
    assert.equal(snapshot.busyLabel, "");
    assert.equal(snapshot.lastStackCommand, "init");
    assert.equal(snapshot.lastStackResult.exitCode, 1);
    assert.equal(snapshot.readmeExists, false);
  });

  it("prepares the vault but skips preview when the local API is not ready", async function () {
    const vaultPath = await resetVaultAndConfigure();
    await setFakeEnv({ MEMO_STACK_FAKE_LOCAL_STATUS_READY: "false" });

    await browser.executeObsidianCommand("memo-stack:prepare-vault");
    await waitForLocalStackCalls(vaultPath, 2);
    await waitForCliCalls(vaultPath, 1);
    await browser.pause(150);

    assert.deepEqual(
      readLocalStackCalls(vaultPath).map((call) => `${call.command}:${call.status}`),
      ["init:0", "status:0"],
    );
    assert.deepEqual(
      readCliCalls(vaultPath).map((call) => `${call.command}:${call.status}`),
      ["connect:0"],
    );

    const snapshot = await memoStackSnapshot();
    assert.equal(snapshot.busyLabel, "");
    assert.equal(snapshot.lastCommand, "connect");
    assert.equal(snapshot.lastStackCommand, "status");
    assert.equal(snapshot.lastStackResult.payload.health.status_code, 503);
    assert.equal(snapshot.readmeExists, true);
    assert.equal(snapshot.inboxExists, true);

    await browser.executeObsidianCommand("memo-stack:open-inbox");
    const activeInboxPath = await browser.executeObsidian(({ app }) => {
      return app.workspace.getActiveFile()?.path ?? "";
    });
    assert.equal(
      activeInboxPath,
      ["Memo Stack", "spaces", spaceSlug, "profiles", profileExternalRef, "inbox", "README.md"].join("/"),
    );
  });
});

async function resetVaultAndConfigure(
  overrides: Partial<{
    applyImportOnSync: boolean;
    commandTimeoutMs: number;
  }> = {},
): Promise<string> {
  const obsidianPage = await browser.getObsidianPage();
  await obsidianPage.resetVault({
    "Welcome.md": "# Welcome\n\nPlugin command E2E vault.\n",
  });
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
      applyImportOnSync: overrides.applyImportOnSync ?? true,
      commandTimeoutMs: overrides.commandTimeoutMs ?? 10000,
    },
  );
  return vaultPath;
}

async function setFakeEnv(values: Record<string, string>): Promise<void> {
  await browser.executeObsidian(
    (_context, payload) => {
      for (const key of payload.keys) {
        delete process.env[key];
      }
      for (const [key, value] of Object.entries(payload.values)) {
        process.env[key] = String(value);
      }
    },
    { keys: fakeEnvKeys, values },
  );
}

async function clearFakeEnv(): Promise<void> {
  await setFakeEnv({});
}

async function memoStackSnapshot(): Promise<any> {
  return await browser.executeObsidian(({ plugins }) => {
    return (plugins.memoStack as any).snapshot();
  });
}

async function waitForPluginIdle(): Promise<void> {
  await browser.waitUntil(async () => (await memoStackSnapshot()).busyLabel === "", {
    timeout: 10000,
    timeoutMsg: "Memo Stack plugin did not become idle",
  });
}

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
  status: number;
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
  status: number;
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
