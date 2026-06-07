import assert from "node:assert/strict";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { spawn, type ChildProcess } from "node:child_process";
import { browser } from "@wdio/globals";

const repoRoot = path.resolve("../../");
const realCliPath = path.resolve("test/fixtures/real-memo-stack-obsidian.cjs");
const token = "wdio-full-e2e-token";
const spaceSlug = "wdio-full-e2e";
const profileExternalRef = "default";
const rootFolder = "Memo Stack";
const scopedRoot = path.join(
  rootFolder,
  "spaces",
  spaceSlug,
  "profiles",
  profileExternalRef,
);
const textStart = "<!-- memo-stack-managed:fact-text:start -->";
const textEnd = "<!-- memo-stack-managed:fact-text:end -->";
const realEnvKeys = ["MEMO_STACK_REAL_OBSIDIAN_DELAY_MS"];

describe("Memo Stack real sync race E2E", function () {
  let server: ChildProcess | undefined;
  let tempDir = "";
  let baseUrl = "";

  beforeEach(async function () {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "memo-stack-wdio-race-"));
    const port = await freePort();
    baseUrl = `http://127.0.0.1:${port}`;
    server = startMemoStackServer(path.join(tempDir, "memory.db"), port);
    await waitForHealth(baseUrl);
    await clearRealEnv();
  });

  afterEach(async function () {
    await clearRealEnv();
    server?.kill("SIGTERM");
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it("blocks overlapping real sync commands while preserving one backend update", async function () {
    const fact = await createFact(baseUrl, {
      text: "Obsidian WDIO real overlap initial fact.",
      sourceId: "wdio-real-overlap-seed",
    });
    const vaultPath = await resetVaultAndConfigure(baseUrl);
    const exportedFact = await connectAndExportFact(vaultPath);
    const appliedText = "Obsidian WDIO real overlap local edit applied once.";
    replaceManagedText(exportedFact, appliedText);
    await setRealEnv({ MEMO_STACK_REAL_OBSIDIAN_DELAY_MS: "1200" });

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
    await waitForCliCalls(vaultPath, 3);
    await waitForPluginIdle();
    await waitForBackendFactText(baseUrl, fact.id, appliedText);

    const calls = readCliCalls(vaultPath);
    assert.deepEqual(
      calls.map((call) => call.command),
      ["connect", "sync", "sync"],
    );
    assert.ok(calls.every((call) => call.status === 0));
    assert.equal(factFiles(vaultPath).length, 1);
    assert.equal(conflictFiles(vaultPath).length, 0);

    const updatedFact = await getFact(baseUrl, fact.id);
    assert.equal(updatedFact.version, 2);
    assert.equal(updatedFact.text, appliedText);
    const markdown = fs.readFileSync(onlyFactFile(vaultPath), "utf8");
    assert.match(markdown, new RegExp(appliedText));
    assert.match(markdown, /memo_stack_version: 2/);
  });

  it("recovers dirty local edits after the backend dies during real sync", async function () {
    const dbPath = path.join(tempDir, "memory.db");
    const port = Number(new URL(baseUrl).port);
    const fact = await createFact(baseUrl, {
      text: "Obsidian WDIO backend restart initial fact.",
      sourceId: "wdio-backend-restart-seed",
    });
    const vaultPath = await resetVaultAndConfigure(baseUrl);
    const exportedFact = await connectAndExportFact(vaultPath);
    const recoveredText = "Obsidian WDIO backend restart local draft recovered.";
    replaceManagedText(exportedFact, recoveredText);
    await setRealEnv({ MEMO_STACK_REAL_OBSIDIAN_DELAY_MS: "900" });

    const duringSync = await browser.executeObsidian(async ({ plugins }) => {
      const plugin = plugins.memoStack as any;
      void plugin.syncNow();
      await new Promise((resolve) => setTimeout(resolve, 100));
      return plugin.snapshot();
    });
    assert.equal(duringSync.busyLabel, "syncing vault");

    server?.kill("SIGTERM");
    server = undefined;
    await waitForUnhealthy(baseUrl);
    await waitForCliCalls(vaultPath, 3);
    await waitForPluginIdle();

    let calls = readCliCalls(vaultPath);
    assert.deepEqual(
      calls.map((call) => call.command),
      ["connect", "sync", "sync"],
    );
    assert.equal(calls.at(-1)?.status, 1);
    assert.match(fs.readFileSync(exportedFact, "utf8"), new RegExp(recoveredText));
    assert.equal(conflictFiles(vaultPath).length, 0);

    await clearRealEnv();
    server = startMemoStackServer(dbPath, port);
    await waitForHealth(baseUrl);

    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 4);
    await waitForPluginIdle();
    await waitForBackendFactText(baseUrl, fact.id, recoveredText);

    calls = readCliCalls(vaultPath);
    assert.equal(calls.at(-1)?.command, "sync");
    assert.equal(calls.at(-1)?.status, 0);
    assert.equal(conflictFiles(vaultPath).length, 0);
    const recoveredFact = await getFact(baseUrl, fact.id);
    assert.equal(recoveredFact.version, 2);
    assert.equal(recoveredFact.text, recoveredText);
    const markdown = fs.readFileSync(onlyFactFile(vaultPath), "utf8");
    assert.match(markdown, new RegExp(recoveredText));
    assert.match(markdown, /memo_stack_version: 2/);
  });
});

async function resetVaultAndConfigure(apiUrl: string): Promise<string> {
  const obsidianPage = await browser.getObsidianPage();
  await obsidianPage.resetVault({
    "Welcome.md": "# Welcome\n\nRace E2E vault.\n",
  });
  const vaultPath = obsidianPage.getVaultPath();
  await configurePlugin(vaultPath, apiUrl);
  return vaultPath;
}

async function connectAndExportFact(vaultPath: string): Promise<string> {
  await browser.executeObsidianCommand("memo-stack:connect-vault");
  await waitForCliCalls(vaultPath, 1);
  await waitForPluginIdle();
  await browser.executeObsidianCommand("memo-stack:sync-now");
  await waitForCliCalls(vaultPath, 2);
  await waitForPluginIdle();
  return onlyFactFile(vaultPath);
}

async function configurePlugin(vaultPath: string, apiUrl: string): Promise<void> {
  const settings = {
    apiUrl,
    token,
    cliPath: realCliPath,
    vaultPathOverride: vaultPath,
    spaceSlug,
    profileExternalRef,
    rootFolder,
    layoutVersion: "v2",
    applyImportOnSync: true,
    commandTimeoutMs: 5000,
  };
  writeVaultFile(
    vaultPath,
    path.join(".obsidian", "plugins", "memo-stack", "data.json"),
    JSON.stringify(settings, null, 2),
  );
  await browser.executeObsidian(
    async ({ plugins }, persistedSettings) => {
      const plugin = plugins.memoStack as any;
      Object.assign(plugin.settings, persistedSettings);
      await plugin.saveSettings();
    },
    settings,
  );
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

async function waitForHealth(apiUrl: string): Promise<void> {
  await waitUntil(async () => {
    try {
      const response = await requestJson("GET", `${apiUrl}/v1/health`);
      return response.status === 200;
    } catch (_error) {
      return false;
    }
  }, "Memo Stack server did not become healthy");
}

async function waitForUnhealthy(apiUrl: string): Promise<void> {
  await waitUntil(async () => {
    try {
      const response = await requestJson("GET", `${apiUrl}/v1/health`);
      return response.status !== 200;
    } catch (_error) {
      return true;
    }
  }, "Memo Stack server stayed healthy");
}

async function createFact(
  apiUrl: string,
  { text, sourceId }: { text: string; sourceId: string },
): Promise<Record<string, any>> {
  const response = await requestJson("POST", `${apiUrl}/v1/facts`, {
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

async function getFact(apiUrl: string, factId: string): Promise<Record<string, any>> {
  const response = await requestJson("GET", `${apiUrl}/v1/facts/${factId}`);
  assert.equal(response.status, 200);
  return response.body.data;
}

async function waitForBackendFactText(
  apiUrl: string,
  factId: string,
  expectedText: string,
): Promise<void> {
  await waitUntil(async () => {
    const fact = await getFact(apiUrl, factId);
    return fact.text === expectedText;
  }, `Backend fact did not reach expected text: ${expectedText}`);
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

async function waitForCliCalls(vaultPath: string, count: number): Promise<void> {
  await browser.waitUntil(() => readCliCalls(vaultPath).length >= count, {
    timeout: 20000,
    timeoutMsg: `Expected ${count} connector CLI calls`,
  });
}

async function waitForPluginIdle(): Promise<void> {
  await browser.waitUntil(async () => (await memoStackSnapshot()).busyLabel === "", {
    timeout: 20000,
    timeoutMsg: "Memo Stack plugin did not become idle",
  });
}

async function memoStackSnapshot(): Promise<any> {
  return await browser.executeObsidian(({ plugins }) => {
    return (plugins.memoStack as any).snapshot();
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

function factFiles(vaultPath: string): string[] {
  const factsDir = path.join(vaultPath, scopedRoot, "generated", "facts");
  if (!fs.existsSync(factsDir)) {
    return [];
  }
  return fs
    .readdirSync(factsDir)
    .filter((name) => name.endsWith(".md") && !name.startsWith("."))
    .map((name) => path.join(factsDir, name));
}

function onlyFactFile(vaultPath: string): string {
  const files = factFiles(vaultPath);
  assert.equal(files.length, 1);
  return files[0];
}

function conflictFiles(vaultPath: string): string[] {
  const conflictsDir = path.join(vaultPath, scopedRoot, "conflicts");
  if (!fs.existsSync(conflictsDir)) {
    return [];
  }
  return fs
    .readdirSync(conflictsDir)
    .filter((name) => name.endsWith(".md") && !name.startsWith(".") && name !== "README.md")
    .map((name) => path.join(conflictsDir, name));
}

function replaceManagedText(filePath: string, text: string): void {
  const old = fs.readFileSync(filePath, "utf8");
  const start = old.indexOf(textStart) + textStart.length;
  const end = old.indexOf(textEnd);
  assert.ok(start >= textStart.length);
  assert.ok(end > start);
  fs.writeFileSync(filePath, `${old.slice(0, start)}\n${text}\n${old.slice(end)}`, "utf8");
}

function writeVaultFile(vaultPath: string, relativePath: string, content: string): void {
  const target = path.join(vaultPath, relativePath);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, content, "utf8");
}

function readCliCalls(vaultPath: string): Array<{ command: string; args: string[]; status: number }> {
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

async function setRealEnv(values: Record<string, string>): Promise<void> {
  await browser.executeObsidian(
    (_context, payload) => {
      for (const key of payload.keys) {
        delete process.env[key];
      }
      for (const [key, value] of Object.entries(payload.values)) {
        process.env[key] = String(value);
      }
    },
    { keys: realEnvKeys, values },
  );
}

async function clearRealEnv(): Promise<void> {
  await setRealEnv({});
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
