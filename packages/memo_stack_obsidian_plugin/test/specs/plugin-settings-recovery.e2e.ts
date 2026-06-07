import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { browser } from "@wdio/globals";

const pluginId = "memo-stack";
const fakeCliPath = path.resolve("test/fixtures/fake-memo-stack-obsidian.cjs");
const fakeLocalCliPath = path.resolve("test/fixtures/fake-memo-stack.cjs");
const defaultApiUrl = "http://127.0.0.1:7788";
const defaultSpaceSlug = "default";
const defaultProfileExternalRef = "default";
const defaultRootFolder = "Memo Stack";

describe("Memo Stack plugin settings recovery E2E", function () {
  it("loads with defaults after malformed data.json and can save usable settings", async function () {
    const obsidianPage = await browser.getObsidianPage();
    await obsidianPage.resetVault({
      "Welcome.md": "# Welcome\n\nMalformed settings E2E vault.\n",
    });
    const vaultPath = obsidianPage.getVaultPath();

    writePluginData(vaultPath, "{ not valid json");
    await browser.reloadObsidian();
    await waitForPluginLoaded();

    let runtime = await pluginRuntime();
    assert.equal(runtime.loaded, true);
    assert.ok(runtime.commandIds.includes("memo-stack:connect-vault"));
    assert.equal(runtime.snapshot.apiUrl, defaultApiUrl);
    assert.equal(runtime.snapshot.spaceSlug, defaultSpaceSlug);
    assert.equal(runtime.snapshot.profileExternalRef, defaultProfileExternalRef);
    assert.equal(runtime.snapshot.rootFolder, defaultRootFolder);
    assert.equal(runtime.snapshot.busyLabel, "");

    const recoveredSettings = {
      apiUrl: "http://127.0.0.1:65531",
      token: "recovered-token",
      localCliPath: fakeLocalCliPath,
      cliPath: fakeCliPath,
      vaultPathOverride: vaultPath,
      spaceSlug: "recovered-project",
      profileExternalRef: "recovered-profile",
      rootFolder: "Recovered Memo",
      layoutVersion: "v2",
      applyImportOnSync: true,
      commandTimeoutMs: 10000,
    };
    await browser.executeObsidian(
      async ({ plugins }, settings) => {
        const plugin = plugins.memoStack as any;
        Object.assign(plugin.settings, settings);
        await plugin.saveSettings();
      },
      recoveredSettings,
    );

    clearMemoStackState(vaultPath);
    await browser.reloadObsidian();
    await browser.waitUntil(async () => (await pluginRuntime()).snapshot.spaceSlug === "recovered-project", {
      timeout: 20000,
      timeoutMsg: "Memo Stack plugin did not reload recovered settings",
    });

    runtime = await pluginRuntime();
    assert.equal(runtime.snapshot.apiUrl, recoveredSettings.apiUrl);
    assert.equal(runtime.snapshot.profileExternalRef, recoveredSettings.profileExternalRef);
    assert.equal(runtime.snapshot.rootFolder, recoveredSettings.rootFolder);

    await browser.executeObsidianCommand("memo-stack:connect-vault");
    await waitForCliCalls(vaultPath, 1);
    await waitForPluginIdle();

    const calls = readCliCalls(vaultPath);
    assert.deepEqual(calls.map((call) => `${call.command}:${call.status}`), ["connect:0"]);
    assert.equal(calls[0].envToken, recoveredSettings.token);
    assert.ok(calls[0].args.includes(recoveredSettings.apiUrl));
    assert.ok(calls[0].args.includes(recoveredSettings.spaceSlug));
    assert.ok(calls[0].args.includes(recoveredSettings.profileExternalRef));
    assert.ok(calls[0].args.includes(recoveredSettings.rootFolder));
    assert.match(readVaultFile(vaultPath, "Recovered Memo/README.md"), /Connected by plugin E2E/);
  });

  it("normalizes invalid persisted setting types after reload", async function () {
    const obsidianPage = await browser.getObsidianPage();
    await obsidianPage.resetVault({
      "Welcome.md": "# Welcome\n\nInvalid setting types E2E vault.\n",
    });
    const vaultPath = obsidianPage.getVaultPath();

    writePluginData(
      vaultPath,
      JSON.stringify(
        {
          apiUrl: 42,
          token: ["not", "a", "token"],
          localCliPath: { bin: fakeLocalCliPath },
          cliPath: fakeCliPath,
          vaultPathOverride: vaultPath,
          rootFolder: "Typed Memo",
          layoutVersion: "v99",
          spaceSlug: 123,
          profileExternalRef: null,
          applyImportOnSync: "true",
          commandTimeoutMs: "fast",
        },
        null,
        2,
      ),
    );

    clearMemoStackState(vaultPath);
    await browser.reloadObsidian();
    await waitForPluginLoaded();

    const runtime = await pluginRuntime();
    assert.equal(runtime.loaded, true);
    assert.equal(runtime.snapshot.apiUrl, defaultApiUrl);
    assert.equal(runtime.snapshot.spaceSlug, defaultSpaceSlug);
    assert.equal(runtime.snapshot.profileExternalRef, defaultProfileExternalRef);
    assert.equal(runtime.snapshot.rootFolder, "Typed Memo");
    assert.equal(runtime.snapshot.layoutVersion, "v2");
    assert.equal(runtime.snapshot.pathError, "");

    await browser.executeObsidianCommand("memo-stack:connect-vault");
    await waitForCliCalls(vaultPath, 1);
    await waitForPluginIdle();

    const calls = readCliCalls(vaultPath);
    assert.deepEqual(calls.map((call) => `${call.command}:${call.status}`), ["connect:0"]);
    assert.equal(calls[0].envToken, "");
    assert.ok(calls[0].args.includes(defaultApiUrl));
    assert.ok(calls[0].args.includes(defaultSpaceSlug));
    assert.ok(calls[0].args.includes(defaultProfileExternalRef));
    assert.ok(calls[0].args.includes("Typed Memo"));
    assert.match(readVaultFile(vaultPath, "Typed Memo/README.md"), /Connected by plugin E2E/);
  });
});

async function waitForPluginLoaded(): Promise<void> {
  await browser.waitUntil(async () => (await pluginRuntime()).loaded, {
    timeout: 20000,
    timeoutMsg: "Memo Stack plugin did not load",
  });
}

async function waitForPluginIdle(): Promise<void> {
  await browser.waitUntil(async () => (await pluginRuntime()).snapshot.busyLabel === "", {
    timeout: 20000,
    timeoutMsg: "Memo Stack plugin did not become idle",
  });
}

async function pluginRuntime(): Promise<{
  loaded: boolean;
  commandIds: string[];
  snapshot: any;
}> {
  return await browser.executeObsidian(({ app, plugins }) => {
    const plugin = (plugins as any).memoStack as any;
    return {
      loaded: Boolean(plugin),
      commandIds: Object.keys((app as any).commands.commands)
        .filter((id) => id.startsWith("memo-stack:"))
        .sort(),
      snapshot: plugin?.snapshot?.() ?? {},
    };
  });
}

async function waitForCliCalls(vaultPath: string, count: number): Promise<void> {
  await browser.waitUntil(() => readCliCalls(vaultPath).length >= count, {
    timeout: 10000,
    timeoutMsg: `Expected ${count} connector CLI calls`,
  });
}

function writePluginData(vaultPath: string, content: string): void {
  writeVaultFile(vaultPath, path.join(".obsidian", "plugins", pluginId, "data.json"), content);
}

function clearMemoStackState(vaultPath: string): void {
  fs.rmSync(path.join(vaultPath, ".memo-stack"), { recursive: true, force: true });
}

function writeVaultFile(vaultPath: string, relativePath: string, content: string): void {
  const target = path.join(vaultPath, relativePath);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, content, "utf8");
}

function readVaultFile(vaultPath: string, relativePath: string): string {
  return fs.readFileSync(path.join(vaultPath, relativePath), "utf8");
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
