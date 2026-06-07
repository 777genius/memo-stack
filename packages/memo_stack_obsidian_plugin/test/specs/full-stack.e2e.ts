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

describe("Memo Stack full Obsidian E2E", function () {
  let server: ChildProcess | undefined;
  let tempDir = "";
  let baseUrl = "";
  let seededFactId = "";

  before(async function () {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "memo-stack-wdio-full-"));
    const port = await freePort();
    baseUrl = `http://127.0.0.1:${port}`;
    server = startMemoStackServer(path.join(tempDir, "memory.db"), port);
    await waitForHealth(baseUrl);
    seededFactId = (await createFact(baseUrl)).id;
  });

  after(function () {
    server?.kill("SIGTERM");
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it("syncs through real Obsidian plugin, connector CLI, HTTP API and vault files", async function () {
    const obsidianPage = await browser.getObsidianPage();
    await obsidianPage.resetVault({
      "Welcome.md": "# Welcome\n\nFull E2E vault.\n",
    });
    const vaultPath = obsidianPage.getVaultPath();

    await configurePlugin(vaultPath, baseUrl);

    await browser.executeObsidianCommand("memo-stack:connect-vault");
    await waitForCliCalls(vaultPath, 1);
    await waitForVaultFile(vaultPath, "Memo Stack/README.md");
    assert.match(readVaultFile(vaultPath, "Memo Stack/README.md"), /Memo Stack/);

    await browser.executeObsidianCommand("memo-stack:preview-sync");
    await waitForCliCalls(vaultPath, 2);
    assert.equal(factFiles(vaultPath).length, 0, "preview must not export fact files");

    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 3);
    const exportedFact = onlyFactFile(vaultPath);
    assert.match(fs.readFileSync(exportedFact, "utf8"), /Obsidian WDIO full E2E initial fact/);

    replaceManagedText(exportedFact, "Obsidian WDIO full E2E updated from markdown.");
    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForBackendFactText(
      baseUrl,
      seededFactId,
      "Obsidian WDIO full E2E updated from markdown.",
    );
    await waitForCliCalls(vaultPath, 4);
    const updatedFact = await getFact(baseUrl, seededFactId);
    assert.equal(updatedFact.version, 2);

    writeVaultFile(
      vaultPath,
      path.join(scopedRoot, "inbox", "full-e2e-inbox.md"),
      "WDIO full E2E inbox marker.",
    );
    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 5);
    await waitForSuggestions(baseUrl, 1);

    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 6);
    await sleep(300);
    assert.equal((await matchingSuggestions(baseUrl)).length, 1);

    await browser.executeObsidianCommand("memo-stack:open-memo-stack-readme");
    const activeFilePath = await browser.executeObsidian(({ app }) => {
      return app.workspace.getActiveFile()?.path ?? "";
    });
    assert.equal(activeFilePath, "Memo Stack/README.md");

    const calls = readCliCalls(vaultPath);
    assert.deepEqual(
      calls.map((call) => call.command),
      ["connect", "preview", "sync", "sync", "sync", "sync"],
    );
    assert.ok(calls.every((call) => call.args.includes("--api-url")));
    assert.ok(calls.every((call) => call.args.includes(baseUrl)));
    assert.ok(calls.every((call) => call.args.includes("--space")));
    assert.ok(calls.every((call) => call.args.includes(spaceSlug)));
    assert.ok(calls.every((call) => call.args.includes("--root-folder")));
    assert.ok(calls.every((call) => call.args.includes(rootFolder)));
    assert.ok(calls.every((call) => call.args.includes("--layout")));
    assert.ok(calls.every((call) => call.args.includes("v2")));
    assert.ok(calls.slice(2).every((call) => call.args.includes("--apply-import")));
  });
});

async function configurePlugin(vaultPath: string, apiUrl: string): Promise<void> {
  await browser.executeObsidian(
    async ({ plugins }, settings) => {
      const plugin = plugins.memoStack as any;
      Object.assign(plugin.settings, settings);
      await plugin.saveSettings();
    },
    {
      apiUrl,
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

async function createFact(apiUrl: string): Promise<Record<string, any>> {
  const response = await requestJson("POST", `${apiUrl}/v1/facts`, {
    space_slug: spaceSlug,
    profile_external_ref: profileExternalRef,
    text: "Obsidian WDIO full E2E initial fact.",
    kind: "note",
    source_refs: [
      {
        source_type: "manual",
        source_id: "wdio-full-e2e-seed",
        quote_preview: "Obsidian WDIO full E2E initial fact.",
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

async function waitForSuggestions(apiUrl: string, count: number): Promise<void> {
  await waitUntil(async () => (await matchingSuggestions(apiUrl)).length >= count, "Suggestion was not created");
}

async function matchingSuggestions(apiUrl: string): Promise<Record<string, any>[]> {
  const query = new URLSearchParams({
    space_slug: spaceSlug,
    profile_external_ref: profileExternalRef,
    status: "pending",
  });
  const response = await requestJson("GET", `${apiUrl}/v1/suggestions?${query.toString()}`);
  assert.equal(response.status, 200);
  return response.body.data.filter((item: Record<string, any>) =>
    String(item.candidate_text).includes("WDIO full E2E inbox marker"),
  );
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

async function waitForVaultFile(vaultPath: string, relativePath: string): Promise<void> {
  await waitUntil(
    async () => fs.existsSync(path.join(vaultPath, relativePath)),
    `Vault file was not created: ${relativePath}`,
  );
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

function replaceManagedText(filePath: string, text: string): void {
  const old = fs.readFileSync(filePath, "utf8");
  const start = old.indexOf(textStart) + textStart.length;
  const end = old.indexOf(textEnd);
  assert.ok(start >= textStart.length);
  assert.ok(end > start);
  fs.writeFileSync(filePath, `${old.slice(0, start)}\n${text}\n${old.slice(end)}`, "utf8");
}

function readVaultFile(vaultPath: string, relativePath: string): string {
  return fs.readFileSync(path.join(vaultPath, relativePath), "utf8");
}

function writeVaultFile(vaultPath: string, relativePath: string, content: string): void {
  const target = path.join(vaultPath, relativePath);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, content, "utf8");
}

function readCliCalls(vaultPath: string): Array<{ command: string; args: string[] }> {
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
