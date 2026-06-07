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

  beforeEach(async function () {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "memo-stack-wdio-full-"));
    const port = await freePort();
    baseUrl = `http://127.0.0.1:${port}`;
    server = startMemoStackServer(path.join(tempDir, "memory.db"), port);
    await waitForHealth(baseUrl);
  });

  afterEach(function () {
    server?.kill("SIGTERM");
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it("syncs through real Obsidian plugin, connector CLI, HTTP API and vault files", async function () {
    const seededFact = await createFact(baseUrl, {
      text: "Obsidian WDIO full E2E initial fact.",
      sourceId: "wdio-full-e2e-seed",
    });
    const seededFactId = seededFact.id;
    const vaultPath = await resetVaultAndConfigure(baseUrl);

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
    await waitForSuggestionsContaining(baseUrl, "WDIO full E2E inbox marker", 1);

    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 6);
    await sleep(300);
    assert.equal((await suggestionsContaining(baseUrl, "WDIO full E2E inbox marker")).length, 1);

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
    assert.ok(calls.every((call) => call.status === 0));
  });

  it("surfaces stale direct-edit conflicts without overwriting local notes", async function () {
    const fact = await createFact(baseUrl, {
      text: "Obsidian WDIO stale initial fact.",
      sourceId: "wdio-stale-seed",
    });
    const vaultPath = await resetVaultAndConfigure(baseUrl);
    const exportedFact = await connectAndExportFact(vaultPath);

    replaceManagedText(exportedFact, "Obsidian WDIO stale local draft should survive.");
    const backendUpdate = await updateFact(baseUrl, fact.id, {
      expectedVersion: fact.version,
      text: "Obsidian WDIO stale backend moved first.",
      reason: "External WDIO stale update",
    });
    assert.equal(backendUpdate.version, 2);

    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 3);

    const calls = readCliCalls(vaultPath);
    assert.equal(calls.at(-1)?.command, "sync");
    assert.equal(calls.at(-1)?.status, 1);
    assert.match(fs.readFileSync(exportedFact, "utf8"), /stale local draft should survive/);
    assert.equal((await getFact(baseUrl, fact.id)).text, "Obsidian WDIO stale backend moved first.");

    const conflicts = conflictFiles(vaultPath);
    assert.equal(conflicts.length, 1);
    const conflict = fs.readFileSync(conflicts[0], "utf8");
    assert.match(conflict, /Memo Stack Sync Conflict/);
    assert.match(conflict, /Stale version/);
    assert.match(conflict, new RegExp(fact.id));
  });

  it("keeps dry-run sync from applying direct managed note edits", async function () {
    const fact = await createFact(baseUrl, {
      text: "Obsidian WDIO dry-run initial fact.",
      sourceId: "wdio-dry-run-seed",
    });
    const vaultPath = await resetVaultAndConfigure(baseUrl, false);
    const exportedFact = await connectAndExportFact(vaultPath);

    replaceManagedText(exportedFact, "Obsidian WDIO dry-run local draft must not apply.");
    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 3);

    const calls = readCliCalls(vaultPath);
    assert.equal(calls.at(-1)?.command, "sync");
    assert.equal(calls.at(-1)?.status, 1);
    assert.ok(!calls.at(-1)?.args.includes("--apply-import"));
    assert.equal((await getFact(baseUrl, fact.id)).text, "Obsidian WDIO dry-run initial fact.");
    assert.match(fs.readFileSync(exportedFact, "utf8"), /dry-run local draft must not apply/);
    assert.equal(conflictFiles(vaultPath).length, 0);
  });

  it("imports legacy inbox notes once under the v2 layout", async function () {
    await createFact(baseUrl, {
      text: "Obsidian WDIO legacy inbox scope seed.",
      sourceId: "wdio-legacy-inbox-seed",
    });
    const vaultPath = await resetVaultAndConfigure(baseUrl);
    await connectAndExportFact(vaultPath);

    const marker = "WDIO legacy inbox marker";
    writeVaultFile(vaultPath, path.join(rootFolder, "inbox", "legacy-e2e-inbox.md"), marker);

    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 3);
    await waitForSuggestionsContaining(baseUrl, marker, 1);

    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 4);
    await sleep(300);

    const calls = readCliCalls(vaultPath);
    assert.ok(calls.slice(2).every((call) => call.status === 0));
    assert.equal((await suggestionsContaining(baseUrl, marker)).length, 1);
  });

  it("turns oversized inbox notes into visible conflict artifacts without suggestions", async function () {
    await createFact(baseUrl, {
      text: "Obsidian WDIO oversized inbox scope seed.",
      sourceId: "wdio-oversized-inbox-seed",
    });
    const vaultPath = await resetVaultAndConfigure(baseUrl);
    await connectAndExportFact(vaultPath);

    const marker = "WDIO oversized inbox marker";
    writeVaultFile(
      vaultPath,
      path.join(scopedRoot, "inbox", "oversized-e2e-inbox.md"),
      `${marker} ${"x".repeat(4001)}`,
    );

    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 3);

    const calls = readCliCalls(vaultPath);
    assert.equal(calls.at(-1)?.command, "sync");
    assert.equal(calls.at(-1)?.status, 1);
    assert.equal((await suggestionsContaining(baseUrl, marker)).length, 0);

    const conflicts = conflictFiles(vaultPath);
    assert.equal(conflicts.length, 1);
    const conflict = fs.readFileSync(conflicts[0], "utf8");
    assert.match(conflict, /Inbox note is too large/);
    assert.match(conflict, /oversized-e2e-inbox\.md/);
  });

  it("removes clean exported notes after backend facts are deleted", async function () {
    const fact = await createFact(baseUrl, {
      text: "Obsidian WDIO backend delete target.",
      sourceId: "wdio-backend-delete-seed",
    });
    const vaultPath = await resetVaultAndConfigure(baseUrl);
    const exportedFact = await connectAndExportFact(vaultPath);
    assert.equal(fs.existsSync(exportedFact), true);

    const deleted = await deleteFact(baseUrl, fact.id);
    assert.equal(deleted.status, "deleted");

    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 3);

    const calls = readCliCalls(vaultPath);
    assert.equal(calls.at(-1)?.command, "sync");
    assert.equal(calls.at(-1)?.status, 0);
    assert.equal(fs.existsSync(exportedFact), false);
    assert.equal(factFiles(vaultPath).length, 0);
    assert.equal((await getFact(baseUrl, fact.id)).status, "deleted");
  });

  it("keeps dirty local notes visible when backend facts are deleted", async function () {
    const fact = await createFact(baseUrl, {
      text: "Obsidian WDIO dirty delete-race initial fact.",
      sourceId: "wdio-dirty-delete-race-seed",
    });
    const vaultPath = await resetVaultAndConfigure(baseUrl);
    const exportedFact = await connectAndExportFact(vaultPath);
    replaceManagedText(exportedFact, "Obsidian WDIO dirty delete-race local draft survives.");

    const deleted = await deleteFact(baseUrl, fact.id);
    assert.equal(deleted.status, "deleted");

    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 3);

    const calls = readCliCalls(vaultPath);
    assert.equal(calls.at(-1)?.command, "sync");
    assert.equal(calls.at(-1)?.status, 1);
    assert.match(
      fs.readFileSync(exportedFact, "utf8"),
      /dirty delete-race local draft survives/,
    );
    assert.equal((await getFact(baseUrl, fact.id)).status, "deleted");

    const conflicts = conflictFiles(vaultPath);
    assert.equal(conflicts.length, 1);
    const conflict = fs.readFileSync(conflicts[0], "utf8");
    assert.match(conflict, /Memo Stack Sync Conflict/);
    assert.match(conflict, /Stale version/);
    assert.match(conflict, new RegExp(fact.id));
  });

  it("exports only the configured project and profile scope", async function () {
    const scopedFact = await createFact(baseUrl, {
      text: "Obsidian WDIO scoped export visible fact.",
      sourceId: "wdio-scope-visible-seed",
    });
    const otherSpace = "wdio-other-space";
    const otherProfile = "other-profile";
    await createFact(baseUrl, {
      text: "Obsidian WDIO other scope hidden fact.",
      sourceId: "wdio-scope-hidden-seed",
      space: otherSpace,
      profile: otherProfile,
    });
    const vaultPath = await resetVaultAndConfigure(baseUrl);

    await browser.executeObsidianCommand("memo-stack:connect-vault");
    await waitForCliCalls(vaultPath, 1);
    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 2);

    const exportedFact = onlyFactFile(vaultPath);
    const exportedMarkdown = fs.readFileSync(exportedFact, "utf8");
    assert.match(exportedMarkdown, /Obsidian WDIO scoped export visible fact/);
    assert.doesNotMatch(exportedMarkdown, /Obsidian WDIO other scope hidden fact/);
    assert.equal(
      (await getFact(baseUrl, scopedFact.id)).text,
      "Obsidian WDIO scoped export visible fact.",
    );
    assert.equal(
      fs.existsSync(
        path.join(vaultPath, rootFolder, "spaces", otherSpace, "profiles", otherProfile),
      ),
      false,
    );

    const calls = readCliCalls(vaultPath);
    assert.ok(calls.every((call) => call.args.includes("--space")));
    assert.ok(calls.every((call) => call.args.includes(spaceSlug)));
    assert.ok(!calls.some((call) => call.args.includes(otherSpace)));
  });

  it("turns corrupt managed notes into visible conflicts without overwriting them", async function () {
    const fact = await createFact(baseUrl, {
      text: "Obsidian WDIO corrupt note initial fact.",
      sourceId: "wdio-corrupt-note-seed",
    });
    const vaultPath = await resetVaultAndConfigure(baseUrl);
    const exportedFact = await connectAndExportFact(vaultPath);
    fs.writeFileSync(exportedFact, "not a memo stack fact note", "utf8");

    await updateFact(baseUrl, fact.id, {
      expectedVersion: fact.version,
      text: "Obsidian WDIO corrupt note backend update.",
      reason: "External WDIO corrupt note update",
    });

    await browser.executeObsidianCommand("memo-stack:sync-now");
    await waitForCliCalls(vaultPath, 3);

    const calls = readCliCalls(vaultPath);
    assert.equal(calls.at(-1)?.command, "sync");
    assert.equal(calls.at(-1)?.status, 1);
    assert.equal(fs.readFileSync(exportedFact, "utf8"), "not a memo stack fact note");
    assert.equal(
      (await getFact(baseUrl, fact.id)).text,
      "Obsidian WDIO corrupt note backend update.",
    );

    const conflicts = conflictFiles(vaultPath);
    assert.equal(conflicts.length, 1);
    const conflict = fs.readFileSync(conflicts[0], "utf8");
    assert.match(conflict, /Memo Stack Sync Conflict/);
    assert.match(conflict, /Unsupported note schema: missing/);
  });
});

async function resetVaultAndConfigure(apiUrl: string, applyImportOnSync = true): Promise<string> {
  const obsidianPage = await browser.getObsidianPage();
  await obsidianPage.resetVault({
    "Welcome.md": "# Welcome\n\nFull E2E vault.\n",
  });
  const vaultPath = obsidianPage.getVaultPath();
  await configurePlugin(vaultPath, apiUrl, applyImportOnSync);
  return vaultPath;
}

async function connectAndExportFact(vaultPath: string): Promise<string> {
  await browser.executeObsidianCommand("memo-stack:connect-vault");
  await waitForCliCalls(vaultPath, 1);
  await browser.executeObsidianCommand("memo-stack:sync-now");
  await waitForCliCalls(vaultPath, 2);
  return onlyFactFile(vaultPath);
}

async function configurePlugin(
  vaultPath: string,
  apiUrl: string,
  applyImportOnSync = true,
): Promise<void> {
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
      applyImportOnSync,
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

async function createFact(
  apiUrl: string,
  {
    text,
    sourceId,
    space = spaceSlug,
    profile = profileExternalRef,
  }: {
    text: string;
    sourceId: string;
    space?: string;
    profile?: string;
  },
): Promise<Record<string, any>> {
  const response = await requestJson("POST", `${apiUrl}/v1/facts`, {
    space_slug: space,
    profile_external_ref: profile,
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

async function updateFact(
  apiUrl: string,
  factId: string,
  {
    expectedVersion,
    text,
    reason,
  }: {
    expectedVersion: number;
    text: string;
    reason: string;
  },
): Promise<Record<string, any>> {
  const response = await requestJson("PATCH", `${apiUrl}/v1/facts/${factId}`, {
    expected_version: expectedVersion,
    text,
    reason,
    source_refs: [
      {
        source_type: "manual",
        source_id: `${factId}-external-wdio`,
        quote_preview: text,
      },
    ],
  });
  assert.equal(response.status, 200);
  return response.body.data;
}

async function getFact(apiUrl: string, factId: string): Promise<Record<string, any>> {
  const response = await requestJson("GET", `${apiUrl}/v1/facts/${factId}`);
  assert.equal(response.status, 200);
  return response.body.data;
}

async function deleteFact(apiUrl: string, factId: string): Promise<Record<string, any>> {
  const response = await requestJson("DELETE", `${apiUrl}/v1/facts/${factId}`);
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
    space_slug: spaceSlug,
    profile_external_ref: profileExternalRef,
    status: "pending",
  });
  const response = await requestJson("GET", `${apiUrl}/v1/suggestions?${query.toString()}`);
  assert.equal(response.status, 200);
  return response.body.data.filter((item: Record<string, any>) =>
    String(item.candidate_text).includes(marker),
  );
}

async function requestJson(
  method: "GET" | "POST" | "PATCH" | "DELETE",
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
