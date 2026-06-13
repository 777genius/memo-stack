import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { browser } from "@wdio/globals";

const fakeCliPath = path.resolve("test/fixtures/fake-memo-stack-obsidian.cjs");
const fakeLocalCliPath = path.resolve("test/fixtures/fake-memo-stack.cjs");
const spaceSlug = "wdio-e2e";
const memoryScopeExternalRef = "default";
const pluginId = "memo-stack";
const factsDir = path.join(
  "Memo Stack",
  "spaces",
  spaceSlug,
  "memory_scopes",
  memoryScopeExternalRef,
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
    await waitForPluginIdle();
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
    await waitForPluginIdle();
    await browser.executeObsidianCommand("memo-stack:local-stack-status");
    await waitForLocalStackCalls(vaultPath, 4);
    await waitForPluginIdle();
    await browser.executeObsidianCommand("memo-stack:start-local-stack-lite");
    await waitForLocalStackCalls(vaultPath, 5);
    await waitForPluginIdle();
    await browser.executeObsidianCommand("memo-stack:start-local-stack-lite");
    await browser.pause(300);
    assert.equal(readLocalStackCalls(vaultPath).length, 5);

    await browser.executeObsidianCommand("memo-stack:connect-vault");
    await waitForCliCalls(vaultPath, 3);
    await waitForPluginIdle();
    const readme = readVaultFile(vaultPath, "Memo Stack/README.md");
    assert.match(readme, /Connected by plugin E2E/);

    await browser.executeObsidianCommand("memo-stack:run-doctor");
    await waitForCliCalls(vaultPath, 4);
    await waitForPluginIdle();
    await browser.executeObsidianCommand("memo-stack:preview-sync");
    await waitForCliCalls(vaultPath, 5);
    await waitForPluginIdle();
    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 6);
    await waitForPluginIdle();
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
      ["Memo Stack", "spaces", spaceSlug, "memory_scopes", memoryScopeExternalRef, "conflicts", "README.md"].join("/"),
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

  it("keeps Control Center actions disabled while busy and shows local stack cooldown", async function () {
    const vaultPath = await resetVaultAndConfigure({ commandTimeoutMs: 5000 });
    await resetStartLiteCooldown();

    await browser.executeObsidianCommand("memo-stack:open-control-center");
    await waitForPanelText("Local stack");

    await clickPanelButton("Status");
    await waitForLocalStackCalls(vaultPath, 1);
    await waitForPluginIdle();
    await waitForPanelText("Local stack: ok");

    await setFakeEnv({ MEMO_STACK_FAKE_OBSIDIAN_DELAY_MS: "1200" });
    await clickPanelButton("Sync");
    try {
      await waitForPanelText("Running: syncing vault");
      const panel = await panelState();
      assert.equal(panel.buttons.Sync.disabled, true);
      assert.equal(panel.buttons.Connect.disabled, true);
      assert.equal(panel.buttons.Preview.disabled, true);
      assert.equal(panel.buttons.Health.disabled, true);
      assert.equal(panel.buttons["Start lite"].disabled, true);
    } finally {
      await waitForCliCalls(vaultPath, 1);
      await waitForPluginIdle();
      await clearFakeEnv();
    }
    await waitForPanelText("Last run: ok");

    await clickPanelButton("Start lite");
    await waitForLocalStackCalls(vaultPath, 2);
    await waitForPluginIdle();
    await waitForStartLiteCooldown();

    const panel = await panelState();
    const startLiteKey = Object.keys(panel.buttons).find((label) => label.startsWith("Start lite "));
    assert.ok(startLiteKey, "Control Center must show Start lite cooldown seconds");
    assert.equal(panel.buttons[startLiteKey].disabled, true);
    assert.deepEqual(
      readLocalStackCalls(vaultPath).map((call) => call.args.join(" ")),
      ["status --json", "up --lite"],
    );
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

  it("handles a missing connector binary without leaving the plugin busy", async function () {
    const vaultPath = await resetVaultAndConfigure({
      cliPath: path.join(vaultPathPlaceholder(), "missing-memo-stack-obsidian"),
    });

    await browser.executeObsidianCommand("memo-stack:preview-sync");
    await waitForPluginIdle();
    const snapshot = await memoStackSnapshot();

    assert.equal(readCliCalls(vaultPath).length, 0);
    assert.equal(snapshot.busyLabel, "");
    assert.equal(snapshot.lastCommand, "preview");
    assert.equal(snapshot.lastResult.exitCode, 1);
  });

  it("clears busy state when a connector command times out", async function () {
    const vaultPath = await resetVaultAndConfigure({ commandTimeoutMs: 1000 });
    await setFakeEnv({ MEMO_STACK_FAKE_OBSIDIAN_DELAY_MS: "5000" });

    await browser.executeObsidianCommand("memo-stack:preview-sync");
    await waitForPluginIdle();
    const snapshot = await memoStackSnapshot();

    assert.equal(readCliCalls(vaultPath).length, 0);
    assert.equal(snapshot.busyLabel, "");
    assert.equal(snapshot.lastCommand, "preview");
    assert.equal(snapshot.lastResult.exitCode, 1);
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
      ["Memo Stack", "spaces", spaceSlug, "memory_scopes", memoryScopeExternalRef, "inbox", "README.md"].join("/"),
    );
  });

  it("loads persisted install settings after an Obsidian reload", async function () {
    const obsidianPage = await browser.getObsidianPage();
    await obsidianPage.resetVault({
      "Welcome.md": "# Welcome\n\nPersisted settings E2E vault.\n",
    });
    const vaultPath = obsidianPage.getVaultPath();
    const persistedSpaceSlug = "persisted-project";
    const persistedMemoryScopeRef = "persisted-memory_scope";
    const persistedRoot = "Persisted Memo";
    const persistedFactsDir = path.join(
      persistedRoot,
      "spaces",
      persistedSpaceSlug,
      "memory_scopes",
      persistedMemoryScopeRef,
      "generated",
      "facts",
    );

    writeVaultFile(
      vaultPath,
      path.join(".obsidian", "plugins", pluginId, "data.json"),
      JSON.stringify(
        {
          apiUrl: "http://127.0.0.1:65534",
          token: "persisted-token",
          localCliPath: fakeLocalCliPath,
          cliPath: fakeCliPath,
          vaultPathOverride: path.resolve(vaultPath),
          spaceSlug: persistedSpaceSlug,
          memoryScopeExternalRef: persistedMemoryScopeRef,
          rootFolder: persistedRoot,
          layoutVersion: "v2",
          applyImportOnSync: false,
          commandTimeoutMs: 10000,
        },
        null,
        2,
      ),
    );

    await browser.reloadObsidian();
    await browser.waitUntil(async () => (await memoStackSnapshot()).spaceSlug === persistedSpaceSlug, {
      timeout: 20000,
      timeoutMsg: "Memo Stack plugin did not reload persisted settings",
    });

    const snapshot = await memoStackSnapshot();
    assert.equal(snapshot.apiUrl, "http://127.0.0.1:65534");
    assert.equal(snapshot.spaceSlug, persistedSpaceSlug);
    assert.equal(snapshot.memoryScopeExternalRef, persistedMemoryScopeRef);
    assert.equal(snapshot.rootFolder, persistedRoot);

    await browser.executeObsidianCommand("memo-stack:connect-vault");
    await waitForCliCalls(vaultPath, 1);
    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 2);

    const calls = readCliCalls(vaultPath);
    assert.deepEqual(calls.map((call) => call.command), ["connect", "sync"]);
    assert.equal(calls[0].envToken, "persisted-token");
    assert.ok(calls.every((call) => call.args.includes("--api-url")));
    assert.ok(calls.every((call) => call.args.includes("http://127.0.0.1:65534")));
    assert.ok(calls.every((call) => call.args.includes("--space")));
    assert.ok(calls.every((call) => call.args.includes(persistedSpaceSlug)));
    assert.ok(calls.every((call) => call.args.includes("--memory_scope")));
    assert.ok(calls.every((call) => call.args.includes(persistedMemoryScopeRef)));
    assert.ok(calls.every((call) => call.args.includes("--root-folder")));
    assert.ok(calls.every((call) => call.args.includes(persistedRoot)));
    assert.ok(!calls[1].args.includes("--apply-import"));

    const fact = readVaultFile(vaultPath, path.join(persistedFactsDir, "plugin-e2e.md"));
    assert.match(fact, /Plugin E2E fact/);
  });

  it("survives invalid persisted layout settings after an Obsidian reload", async function () {
    const obsidianPage = await browser.getObsidianPage();
    await obsidianPage.resetVault({
      "Welcome.md": "# Welcome\n\nInvalid persisted settings E2E vault.\n",
    });
    const vaultPath = obsidianPage.getVaultPath();

    writeVaultFile(
      vaultPath,
      path.join(".obsidian", "plugins", pluginId, "data.json"),
      JSON.stringify(
        {
          apiUrl: "http://127.0.0.1:65533",
          token: "invalid-layout-token",
          localCliPath: fakeLocalCliPath,
          cliPath: fakeCliPath,
          vaultPathOverride: path.resolve(vaultPath),
          spaceSlug,
          memoryScopeExternalRef,
          rootFolder: "../escape",
          layoutVersion: "v2",
          applyImportOnSync: true,
          commandTimeoutMs: 10000,
        },
        null,
        2,
      ),
    );

    await browser.reloadObsidian();
    await browser.waitUntil(async () => (await memoStackSnapshot()).rootFolder === "../escape", {
      timeout: 20000,
      timeoutMsg: "Memo Stack plugin did not reload invalid persisted settings",
    });

    const snapshot = await memoStackSnapshot();
    assert.equal(snapshot.busyLabel, "");
    assert.equal(snapshot.rootFolder, "../escape");
    assert.match(snapshot.pathError, /Folder cannot contain/);
    assert.equal(snapshot.readmeExists, false);

    await browser.executeObsidianCommand("memo-stack:open-inbox");
    const calls = readCliCalls(vaultPath);
    assert.equal(calls.length, 0);
  });
});

async function resetVaultAndConfigure(
  overrides: Partial<{
    applyImportOnSync: boolean;
    commandTimeoutMs: number;
    cliPath: string;
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
      cliPath: overrides.cliPath ?? fakeCliPath,
      vaultPathOverride: vaultPath,
      spaceSlug,
      memoryScopeExternalRef,
      rootFolder: "Memo Stack",
      layoutVersion: "v2",
      applyImportOnSync: overrides.applyImportOnSync ?? true,
      commandTimeoutMs: overrides.commandTimeoutMs ?? 10000,
    },
  );
  return vaultPath;
}

function vaultPathPlaceholder(): string {
  return path.resolve("test", "missing-bin");
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

async function resetStartLiteCooldown(): Promise<void> {
  await browser.executeObsidian(({ plugins }) => {
    (plugins.memoStack as any).lastStartLiteAt = 0;
  });
}

async function panelState(): Promise<{
  text: string;
  buttons: Record<string, { disabled: boolean }>;
}> {
  return await browser.execute(() => {
    const panel = document.querySelector(".memo-stack-panel");
    if (!panel) {
      return { text: "", buttons: {} };
    }
    const buttons: Record<string, { disabled: boolean }> = {};
    for (const button of Array.from(panel.querySelectorAll("button"))) {
      const key = button.textContent?.trim() || "";
      buttons[key] = { disabled: (button as HTMLButtonElement).disabled };
    }
    return {
      text: ((panel as HTMLElement).innerText || panel.textContent || "")
        .replace(/\s+/g, " ")
        .trim(),
      buttons,
    };
  });
}

async function waitForPanelText(text: string): Promise<void> {
  await browser.waitUntil(async () => (await panelState()).text.includes(text), {
    timeout: 10000,
    timeoutMsg: `Control Center panel did not contain: ${text}`,
  });
}

async function waitForStartLiteCooldown(): Promise<void> {
  await browser.waitUntil(
    async () =>
      Object.entries((await panelState()).buttons).some(
        ([label, state]) => label.startsWith("Start lite ") && state.disabled,
      ),
    {
      timeout: 10000,
      timeoutMsg: "Control Center did not show Start lite cooldown",
    },
  );
}

async function clickPanelButton(label: string): Promise<void> {
  await browser.waitUntil(async () => {
    return await browser.execute((buttonLabel) => {
      const buttons = Array.from(
        document.querySelectorAll(".memo-stack-panel button"),
      ) as HTMLButtonElement[];
      return buttons.some((button) => button.textContent?.trim() === buttonLabel && !button.disabled);
    }, label);
  }, {
    timeout: 10000,
    timeoutMsg: `Control Center button was not clickable: ${label}`,
  });
  await browser.execute((buttonLabel) => {
    const buttons = Array.from(
      document.querySelectorAll(".memo-stack-panel button"),
    ) as HTMLButtonElement[];
    const button = buttons.find((item) => item.textContent?.trim() === buttonLabel && !item.disabled);
    if (!button) {
      throw new Error(`Button not found: ${buttonLabel}`);
    }
    button.click();
  }, label);
}

function writeVaultFile(vaultPath: string, relativePath: string, content: string): void {
  const target = path.join(vaultPath, relativePath);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, content, "utf8");
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
