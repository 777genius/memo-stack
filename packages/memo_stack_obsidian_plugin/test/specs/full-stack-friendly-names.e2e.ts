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
const realCliPath = path.resolve("test/fixtures/real-memo-stack-obsidian.cjs");
const token = "wdio-full-e2e-token";
const rawSpaceSlug = "Client Alpha / Research 2026";
const rawProfileExternalRef = "Default User+Agent";
const rootFolder = "Team Memory";
const safeSpaceSlug = safeScopeSegment(rawSpaceSlug);
const safeProfileExternalRef = safeScopeSegment(rawProfileExternalRef);
const scopedRoot = path.join(
  rootFolder,
  "spaces",
  safeSpaceSlug,
  "profiles",
  safeProfileExternalRef,
);

describe("Memo Stack friendly project names E2E", function () {
  let server: ChildProcess | undefined;
  let tempDir = "";
  let baseUrl = "";

  beforeEach(async function () {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "memo-stack-wdio-friendly-names-"));
    const port = await freePort();
    baseUrl = `http://127.0.0.1:${port}`;
    server = startMemoStackServer(path.join(tempDir, "memory.db"), port);
    await waitForHealth(baseUrl);
  });

  afterEach(function () {
    server?.kill("SIGTERM");
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it("stores friendly project and profile names in safe scoped vault folders", async function () {
    const fact = await createFact(baseUrl, {
      text: "Obsidian WDIO friendly project visible fact.",
      sourceId: "wdio-friendly-names-seed",
    });
    const vaultPath = await resetVaultAndConfigure(baseUrl);

    await browser.executeObsidianCommand("memo-stack:connect-vault");
    await waitForCliCalls(vaultPath, 1);
    await waitForPluginIdle();

    let snapshot = await memoStackSnapshot();
    assert.equal(snapshot.spaceSlug, rawSpaceSlug);
    assert.equal(snapshot.profileExternalRef, rawProfileExternalRef);
    assert.equal(snapshot.paths.generatedFacts, posixPath(path.join(scopedRoot, "generated", "facts")));
    assert.equal(snapshot.paths.inbox, posixPath(path.join(scopedRoot, "inbox")));
    assert.equal(snapshot.paths.conflicts, posixPath(path.join(scopedRoot, "conflicts")));
    assert.equal(snapshot.inboxExists, true);
    assert.equal(snapshot.conflictsExists, true);
    assert.equal(fs.existsSync(path.join(vaultPath, rootFolder, "spaces", "Client Alpha")), false);

    await browser.executeObsidianCommand("memo-stack:preview-sync");
    await waitForCliCalls(vaultPath, 2);
    await waitForPluginIdle();
    assert.equal(factFiles(vaultPath).length, 0, "friendly-name preview must not export facts");

    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 3);
    await waitForPluginIdle();

    const exportedFact = onlyFactFile(vaultPath);
    assert.equal(path.dirname(exportedFact), path.join(vaultPath, scopedRoot, "generated", "facts"));
    assert.match(fs.readFileSync(exportedFact, "utf8"), /friendly project visible fact/);
    assert.match(fs.readFileSync(exportedFact, "utf8"), /memo_stack_space_slug: Client Alpha \/ Research 2026/);
    assert.match(fs.readFileSync(exportedFact, "utf8"), /memo_stack_profile_external_ref: Default User\+Agent/);
    assert.equal((await getFact(baseUrl, fact.id)).text, "Obsidian WDIO friendly project visible fact.");

    const inboxMarker = "WDIO friendly project inbox marker";
    writeVaultFile(vaultPath, path.join(scopedRoot, "inbox", "friendly-inbox.md"), inboxMarker);
    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 4);
    await waitForPluginIdle();
    await waitForSuggestionsContaining(baseUrl, inboxMarker, 1);

    await browser.executeObsidianCommand("memo-stack:open-inbox");
    assert.equal(await activeFilePath(), posixPath(path.join(scopedRoot, "inbox", "README.md")));

    snapshot = await memoStackSnapshot();
    assert.equal(snapshot.paths.inbox, posixPath(path.join(scopedRoot, "inbox")));
    assert.equal(conflictFiles(vaultPath).length, 0);

    const calls = readCliCalls(vaultPath);
    assert.deepEqual(calls.map((call) => call.command), ["connect", "preview", "sync", "sync"]);
    assert.ok(calls.every((call) => call.args.includes("--space")));
    assert.ok(calls.every((call) => call.args.includes(rawSpaceSlug)));
    assert.ok(calls.every((call) => call.args.includes("--profile")));
    assert.ok(calls.every((call) => call.args.includes(rawProfileExternalRef)));
    assert.ok(calls.every((call) => call.args.includes("--root-folder")));
    assert.ok(calls.every((call) => call.args.includes(rootFolder)));
    assert.ok(calls.slice(2).every((call) => call.args.includes("--apply-import")));
    assert.ok(calls.every((call) => call.status === 0));
  });
});

async function resetVaultAndConfigure(apiUrl: string): Promise<string> {
  const obsidianPage = await browser.getObsidianPage();
  await obsidianPage.resetVault({
    "Welcome.md": "# Welcome\n\nFriendly names E2E vault.\n",
  });
  const vaultPath = obsidianPage.getVaultPath();
  await configurePlugin(vaultPath, apiUrl);
  return vaultPath;
}

async function configurePlugin(vaultPath: string, apiUrl: string): Promise<void> {
  const settings = {
    apiUrl,
    token,
    cliPath: realCliPath,
    vaultPathOverride: vaultPath,
    spaceSlug: rawSpaceSlug,
    profileExternalRef: rawProfileExternalRef,
    rootFolder,
    layoutVersion: "v2",
    applyImportOnSync: true,
    commandTimeoutMs: 20000,
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

async function createFact(
  apiUrl: string,
  { text, sourceId }: { text: string; sourceId: string },
): Promise<Record<string, any>> {
  const response = await requestJson("POST", `${apiUrl}/v1/facts`, {
    space_slug: rawSpaceSlug,
    profile_external_ref: rawProfileExternalRef,
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

async function waitForSuggestionsContaining(
  apiUrl: string,
  marker: string,
  count: number,
): Promise<void> {
  await waitUntil(
    async () => (await suggestionsContaining(apiUrl, marker)).length >= count,
    "Suggestion was not created",
  );
}

async function suggestionsContaining(apiUrl: string, marker: string): Promise<Record<string, any>[]> {
  const query = new URLSearchParams({
    space_slug: rawSpaceSlug,
    profile_external_ref: rawProfileExternalRef,
    status: "pending",
  });
  const response = await requestJson("GET", `${apiUrl}/v1/suggestions?${query.toString()}`);
  assert.equal(response.status, 200);
  return response.body.data.filter((item: Record<string, any>) =>
    String(item.candidate_text).includes(marker),
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

async function activeFilePath(): Promise<string> {
  return await browser.executeObsidian(({ app }) => app.workspace.getActiveFile()?.path ?? "");
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
    .map((name) => path.join(factsDir, name))
    .sort();
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

function readVaultFile(vaultPath: string, relativePath: string): string {
  return fs.readFileSync(path.join(vaultPath, relativePath), "utf8");
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

function safeScopeSegment(value: string): string {
  const raw = value.trim();
  const normalized = raw.toLocaleLowerCase();
  let slug = normalized.replace(/[^a-z0-9_.-]+/g, "-").replace(/^-+|-+$/g, "");
  slug = slug.replace(/-{2,}/g, "-").replace(/^[._-]+|[._-]+$/g, "");
  if (!slug) {
    slug = "scope";
  }
  const changed = slug !== normalized || slug.length > 72;
  slug = slug.slice(0, 72).replace(/^[._-]+|[._-]+$/g, "") || "scope";
  if (changed) {
    slug = `${slug}--${contentHash(raw).slice(0, 8)}`;
  }
  return slug;
}

function contentHash(value: string): string {
  return crypto
    .createHash("sha256")
    .update(value.replace(/\r\n/g, "\n").replace(/\r/g, "\n"))
    .digest("hex");
}

function posixPath(filePath: string): string {
  return filePath.split(path.sep).join("/");
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
