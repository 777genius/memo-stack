import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { spawn, type ChildProcess } from "node:child_process";
import { browser } from "@wdio/globals";

const repoRoot = path.resolve("../../");
const pluginId = "memo-stack";
const fakeCliPath = path.resolve("test/fixtures/fake-memo-stack-obsidian.cjs");
const realCliPath = path.resolve("test/fixtures/real-memo-stack-obsidian.cjs");
const token = "wdio-packaged-token";
const apiUrl = "http://127.0.0.1:65532";
const spaceSlug = "packaged-project";
const profileExternalRef = "packaged-profile";
const rootFolder = "Packaged Memo";

describe("Memo Stack packaged plugin install E2E", function () {
  it("loads installed package artifacts after reload and runs connector commands", async function () {
    const obsidianPage = await browser.getObsidianPage();
    const vaultPath = obsidianPage.getVaultPath();

    assertInstalledArtifacts(vaultPath);
    let runtime = await pluginRuntime();
    assert.equal(runtime.loaded, true);
    assert.equal(runtime.enabled, true);
    assert.equal(runtime.manifest.id, pluginId);
    assert.equal(runtime.manifest.name, "Memo Stack");
    assert.deepEqual(runtime.commandIds, [
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

    await obsidianPage.resetVault({
      "Welcome.md": "# Welcome\n\nPackaged install E2E vault.\n",
    });
    writeVaultFile(
      vaultPath,
      path.join(".obsidian", "plugins", pluginId, "data.json"),
      JSON.stringify(
        {
          apiUrl,
          token,
          cliPath: fakeCliPath,
          vaultPathOverride: vaultPath,
          spaceSlug,
          profileExternalRef,
          rootFolder,
          layoutVersion: "v2",
          applyImportOnSync: true,
          commandTimeoutMs: 10000,
        },
        null,
        2,
      ),
    );

    await browser.reloadObsidian();
    await browser.waitUntil(async () => (await pluginRuntime()).snapshot.spaceSlug === spaceSlug, {
      timeout: 20000,
      timeoutMsg: "Memo Stack packaged plugin did not reload persisted settings",
    });

    assertInstalledArtifacts(vaultPath);
    runtime = await pluginRuntime();
    assert.equal(runtime.loaded, true);
    assert.equal(runtime.enabled, true);
    assert.equal(runtime.snapshot.apiUrl, apiUrl);
    assert.equal(runtime.snapshot.spaceSlug, spaceSlug);
    assert.equal(runtime.snapshot.profileExternalRef, profileExternalRef);
    assert.equal(runtime.snapshot.rootFolder, rootFolder);

    await obsidianPage.disablePlugin(pluginId);
    await browser.waitUntil(async () => !(await pluginRuntime()).loaded, {
      timeout: 20000,
      timeoutMsg: "Memo Stack packaged plugin did not disable",
    });
    await obsidianPage.enablePlugin(pluginId);
    await browser.waitUntil(async () => (await pluginRuntime()).snapshot.spaceSlug === spaceSlug, {
      timeout: 20000,
      timeoutMsg: "Memo Stack packaged plugin did not enable with persisted settings",
    });

    await browser.executeObsidianCommand("memo-stack:connect-vault");
    await waitForCliCalls(vaultPath, 1);
    await waitForPluginIdle();

    const calls = readCliCalls(vaultPath);
    assert.deepEqual(calls.map((call) => `${call.command}:${call.status}`), ["connect:0"]);
    assert.equal(calls[0].envToken, token);
    assert.ok(calls[0].args.includes("--api-url"));
    assert.ok(calls[0].args.includes(apiUrl));
    assert.ok(calls[0].args.includes("--space"));
    assert.ok(calls[0].args.includes(spaceSlug));
    assert.ok(calls[0].args.includes("--profile"));
    assert.ok(calls[0].args.includes(profileExternalRef));
    assert.ok(calls[0].args.includes("--root-folder"));
    assert.ok(calls[0].args.includes(rootFolder));
    assert.match(readVaultFile(vaultPath, path.join(rootFolder, "README.md")), /Connected by plugin E2E/);

    await browser.executeObsidianCommand("memo-stack:open-control-center");
    const panelOpened = await browser.executeObsidian(({ app }) => {
      return app.workspace.getLeavesOfType("memo-stack-control-center").length === 1;
    });
    assert.equal(panelOpened, true);
  });

  it("loads packaged artifacts and syncs through the real connector and backend", async function () {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "memo-stack-wdio-packaged-real-"));
    const port = await freePort();
    const baseUrl = `http://127.0.0.1:${port}`;
    const server = startMemoStackServer(path.join(tempDir, "memory.db"), port);

    try {
      await waitForHealth(baseUrl);
      const fact = await createFact(baseUrl, {
        text: "Obsidian WDIO packaged real backend fact.",
        sourceId: "wdio-packaged-real-seed",
      });
      const obsidianPage = await browser.getObsidianPage();
      await obsidianPage.resetVault({
        "Welcome.md": "# Welcome\n\nPackaged real sync E2E vault.\n",
      });
      const vaultPath = obsidianPage.getVaultPath();

      writeVaultFile(
        vaultPath,
        path.join(".obsidian", "plugins", pluginId, "data.json"),
        JSON.stringify(
          {
            apiUrl: baseUrl,
            token,
            cliPath: realCliPath,
            vaultPathOverride: vaultPath,
            spaceSlug,
            profileExternalRef,
            rootFolder,
            layoutVersion: "v2",
            applyImportOnSync: true,
            commandTimeoutMs: 20000,
          },
          null,
          2,
        ),
      );

      await browser.reloadObsidian();
      await browser.waitUntil(async () => (await pluginRuntime()).snapshot.apiUrl === baseUrl, {
        timeout: 20000,
        timeoutMsg: "Memo Stack packaged plugin did not reload real sync settings",
      });

      assertInstalledArtifacts(vaultPath);
      let runtime = await pluginRuntime();
      assert.equal(runtime.loaded, true);
      assert.equal(runtime.enabled, true);
      assert.equal(runtime.snapshot.spaceSlug, spaceSlug);
      assert.equal(runtime.snapshot.profileExternalRef, profileExternalRef);
      assert.equal(runtime.snapshot.rootFolder, rootFolder);

      await browser.executeObsidianCommand("memo-stack:connect-vault");
      await waitForRealCliCalls(vaultPath, 1);
      await waitForPluginIdle();
      await browser.executeObsidianCommand("memo-stack:sync-now");
      await waitForRealCliCalls(vaultPath, 2);
      await waitForPluginIdle();

      const calls = readRealCliCalls(vaultPath);
      assert.deepEqual(calls.map((call) => `${call.command}:${call.status}`), ["connect:0", "sync:0"]);
      assert.ok(calls.every((call) => call.args.includes("--api-url")));
      assert.ok(calls.every((call) => call.args.includes(baseUrl)));
      assert.ok(calls.every((call) => call.args.includes("--space")));
      assert.ok(calls.every((call) => call.args.includes(spaceSlug)));
      assert.ok(calls.every((call) => call.args.includes("--profile")));
      assert.ok(calls.every((call) => call.args.includes(profileExternalRef)));
      assert.ok(calls.every((call) => call.args.includes("--root-folder")));
      assert.ok(calls.every((call) => call.args.includes(rootFolder)));

      const exportedFact = onlyFactFile(vaultPath);
      assert.match(fs.readFileSync(exportedFact, "utf8"), /packaged real backend fact/);
      assert.match(fs.readFileSync(exportedFact, "utf8"), new RegExp(`memo_stack_id: ${fact.id}`));

      runtime = await pluginRuntime();
      assert.equal(runtime.snapshot.generatedFactsExists, true);
      assert.equal(runtime.snapshot.lastCommand, "sync");
      assert.equal(runtime.snapshot.lastResult.exitCode, 0);
    } finally {
      server.kill("SIGTERM");
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });
});

function assertInstalledArtifacts(vaultPath: string): void {
  const pluginDir = path.join(vaultPath, ".obsidian", "plugins", pluginId);
  const sourceDir = process.cwd();
  const sourceManifest = readJson(path.join(sourceDir, "manifest.json"));
  const installedManifest = readJson(path.join(pluginDir, "manifest.json"));
  assert.deepEqual(installedManifest, sourceManifest);
  assert.equal(fileHash(path.join(pluginDir, "main.js")), fileHash(path.join(sourceDir, "main.js")));
  assert.equal(fileHash(path.join(pluginDir, "styles.css")), fileHash(path.join(sourceDir, "styles.css")));
  assert.match(fs.readFileSync(path.join(pluginDir, "main.js"), "utf8"), /Memo Stack Obsidian plugin/);

  const communityPlugins = readJson(path.join(vaultPath, ".obsidian", "community-plugins.json"));
  assert.ok(Array.isArray(communityPlugins));
  assert.ok(communityPlugins.includes(pluginId));
}

async function pluginRuntime(): Promise<{
  loaded: boolean;
  enabled: boolean;
  manifest: Record<string, any>;
  commandIds: string[];
  snapshot: any;
}> {
  return await browser.executeObsidian(({ app, plugins }) => {
    const plugin = (plugins as any).memoStack as any;
    const enabledPlugins = Array.from(((app as any).plugins.enabledPlugins ?? []) as Iterable<string>);
    return {
      loaded: Boolean(plugin),
      enabled: enabledPlugins.includes("memo-stack"),
      manifest: (app as any).plugins.manifests["memo-stack"] ?? {},
      commandIds: Object.keys((app as any).commands.commands)
        .filter((id) => id.startsWith("memo-stack:"))
        .sort(),
      snapshot: plugin?.snapshot?.() ?? {},
    };
  });
}

async function waitForPluginIdle(): Promise<void> {
  await browser.waitUntil(async () => (await pluginRuntime()).snapshot.busyLabel === "", {
    timeout: 20000,
    timeoutMsg: "Memo Stack packaged plugin did not become idle",
  });
}

async function waitForCliCalls(vaultPath: string, count: number): Promise<void> {
  await browser.waitUntil(() => readCliCalls(vaultPath).length >= count, {
    timeout: 10000,
    timeoutMsg: `Expected ${count} packaged plugin CLI calls`,
  });
}

async function waitForRealCliCalls(vaultPath: string, count: number): Promise<void> {
  await browser.waitUntil(() => readRealCliCalls(vaultPath).length >= count, {
    timeout: 20000,
    timeoutMsg: `Expected ${count} packaged real connector calls`,
  });
}

async function freePort(): Promise<number> {
  return await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (typeof address !== "object" || address === null) {
        reject(new Error("Could not allocate free port"));
        return;
      }
      const port = address.port;
      server.close(() => resolve(port));
    });
  });
}

function startMemoStackServer(dbPath: string, port: number): ChildProcess {
  const code = `
from memo_stack_server.config import DeployProfile, Settings
from memo_stack_server.main import create_app
import uvicorn

app = create_app(Settings(
    deploy_profile=DeployProfile.TEST,
    database_url="sqlite+aiosqlite:///${dbPath}",
    auto_create_schema=True,
    host="127.0.0.1",
    port=${port},
    service_token="${token}",
    qdrant_enabled=False,
    graphiti_enabled=False,
    embeddings_enabled=False,
    ui_enabled=False,
))
uvicorn.run(app, host="127.0.0.1", port=${port}, log_level="warning")
`;
  return spawn(path.join(repoRoot, ".venv/bin/python"), ["-c", code], {
    cwd: repoRoot,
    env: {
      ...process.env,
      PYTHONPATH: pythonpath(),
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
}

async function waitForHealth(baseUrl: string): Promise<void> {
  await waitUntil(async () => {
    try {
      const response = await requestJson("GET", `${baseUrl}/v1/health`);
      return response.status === 200;
    } catch (_error) {
      return false;
    }
  }, "Memo Stack server did not become healthy");
}

async function createFact(
  baseUrl: string,
  { text, sourceId }: { text: string; sourceId: string },
): Promise<Record<string, any>> {
  const response = await requestJson("POST", `${baseUrl}/v1/facts`, {
    space_slug: spaceSlug,
    profile_external_ref: profileExternalRef,
    text,
    kind: "note",
    source_refs: [
      {
        source_type: "manual",
        source_id: sourceId,
        quote_preview: text,
      },
    ],
  });
  assert.equal(response.status, 201);
  return response.body.data;
}

async function requestJson(
  method: "GET" | "POST",
  url: string,
  body?: Record<string, any>,
): Promise<{ status: number; body: any }> {
  return await new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const requestBody = body ? JSON.stringify(body) : undefined;
    const request = http.request(
      {
        method,
        hostname: parsed.hostname,
        port: parsed.port,
        path: `${parsed.pathname}${parsed.search}`,
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
          ...(requestBody
            ? { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(requestBody) }
            : {}),
        },
      },
      (response) => {
        const chunks: Buffer[] = [];
        response.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
        response.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          resolve({
            status: response.statusCode ?? 0,
            body: text ? JSON.parse(text) : {},
          });
        });
      },
    );
    request.on("error", reject);
    if (requestBody) {
      request.write(requestBody);
    }
    request.end();
  });
}

async function waitUntil(check: () => Promise<boolean>, message: string): Promise<void> {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    if (await check()) {
      return;
    }
    await sleep(150);
  }
  throw new Error(message);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
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

function readRealCliCalls(vaultPath: string): Array<{ command: string; args: string[]; status: number }> {
  const logPath = path.join(vaultPath, ".memo-stack/real-plugin-cli-calls.jsonl");
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

function factFiles(vaultPath: string): string[] {
  const factsDir = path.join(
    vaultPath,
    rootFolder,
    "spaces",
    spaceSlug,
    "profiles",
    profileExternalRef,
    "generated",
    "facts",
  );
  if (!fs.existsSync(factsDir)) {
    return [];
  }
  return fs
    .readdirSync(factsDir)
    .filter((name) => name.endsWith(".md") && !name.startsWith("."))
    .map((name) => path.join(factsDir, name))
    .sort();
}

function onlyFactFile(vaultPath: string): string {
  const files = factFiles(vaultPath);
  assert.equal(files.length, 1);
  return files[0];
}

function readJson(filePath: string): any {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function fileHash(filePath: string): string {
  return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

function pythonpath(): string {
  return [
    "packages/memo_stack_core",
    "packages/memo_stack_adapters",
    "packages/memo_stack_server",
    "packages/memo_stack_sdk",
    "packages/memo_stack_obsidian",
  ]
    .map((relativePath) => path.join(repoRoot, relativePath))
    .join(path.delimiter);
}
