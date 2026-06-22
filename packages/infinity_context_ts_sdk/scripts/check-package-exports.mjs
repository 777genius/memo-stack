import { createRequire } from "node:module";
import { readFile, stat } from "node:fs/promises";

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
}

console.log(`Package exports ok: ${expectedExports.length} entry points, ${expectedBins.length} bins`);
