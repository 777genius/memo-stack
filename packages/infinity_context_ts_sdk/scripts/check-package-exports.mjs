import { execFile } from "node:child_process";
import { createRequire } from "node:module";
import { readFile, stat } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const require = createRequire(import.meta.url);
const packageJson = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));

const expectedExports = [
  ["@infinity-context/sdk", "InfinityContextClient"],
  ["@infinity-context/sdk/instrumentation", "noopInstrumentation"],
  ["@infinity-context/sdk/pagination", "iterateCursorItems"],
  ["@infinity-context/sdk/runtime", "assertFullMemoryReady"],
  ["@infinity-context/sdk/canary", "runRuntimeCanary"],
  ["@infinity-context/sdk/proof", "runFullMemoryProof"],
  ["@infinity-context/sdk/workflows", "MemoryWorkflows"],
];
const expectedBins = [
  ["infinity-context-full-memory-proof", "scripts/full-memory-proof.mjs"],
  ["infinity-context-runtime-canary", "scripts/runtime-canary.mjs"],
];

for (const [specifier, exportName] of expectedExports) {
  const esm = await import(specifier);
  if (typeof esm[exportName] === "undefined") {
    throw new Error(`Missing ESM export ${exportName} from ${specifier}`);
  }

  const cjs = require(specifier);
  if (typeof cjs[exportName] === "undefined") {
    throw new Error(`Missing CJS export ${exportName} from ${specifier}`);
  }
}

for (const [binName, targetPath] of expectedBins) {
  const declaredTarget = packageJson.bin?.[binName];
  if (declaredTarget !== `./${targetPath}`) {
    throw new Error(`Missing package bin ${binName} -> ./${targetPath}`);
  }

  const targetUrl = new URL(`../${targetPath}`, import.meta.url);
  const targetStat = await stat(targetUrl);
  if (!targetStat.isFile()) {
    throw new Error(`Package bin target is not a file: ${targetPath}`);
  }

  const targetText = await readFile(targetUrl, "utf8");
  if (!targetText.startsWith("#!/usr/bin/env node")) {
    throw new Error(`Package bin target is missing node shebang: ${targetPath}`);
  }

  const resolvedTargetPath = fileURLToPath(targetUrl);
  const help = await execFileAsync(process.execPath, [resolvedTargetPath, "--help"]);
  if (help.stderr.trim().length > 0 || !help.stdout.includes(`Usage: ${binName}`)) {
    throw new Error(`Package bin help output is invalid for ${binName}`);
  }

  const version = await execFileAsync(process.execPath, [resolvedTargetPath, "--version"]);
  if (version.stderr.trim().length > 0 || version.stdout.trim() !== packageJson.version) {
    throw new Error(`Package bin version output is invalid for ${binName}`);
  }
}

console.log(`Package exports ok: ${expectedExports.length} entry points, ${expectedBins.length} bins`);
