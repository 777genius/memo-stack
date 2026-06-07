import fs from "node:fs";
import childProcess from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.dirname(fileURLToPath(import.meta.url));
const fakeCliPath = path.resolve(rootDir, "test/fixtures/fake-memo-stack-obsidian.cjs");
const realCliPath = path.resolve(rootDir, "test/fixtures/real-memo-stack-obsidian.cjs");
const defaultMacObsidianApp = "/Applications/Obsidian.app";
const defaultMacBinaryPath = path.join(defaultMacObsidianApp, "Contents/MacOS/Obsidian");
const defaultMacAppPath = path.join(defaultMacObsidianApp, "Contents/Resources/obsidian.asar");

function readMacAppVersion(appPath: string): string | undefined {
  if (process.platform !== "darwin") {
    return undefined;
  }

  try {
    return childProcess
      .execFileSync("/usr/bin/defaults", ["read", path.join(appPath, "Contents/Info"), "CFBundleShortVersionString"], {
        encoding: "utf8",
      })
      .trim();
  } catch {
    return undefined;
  }
}

const localBinaryPath = process.env.MEMO_STACK_OBSIDIAN_BINARY_PATH ?? defaultMacBinaryPath;
const localAppPath = process.env.MEMO_STACK_OBSIDIAN_APP_PATH ?? defaultMacAppPath;
const hasLocalObsidian = fs.existsSync(localBinaryPath) && fs.existsSync(localAppPath);
const localObsidianVersion = hasLocalObsidian
  ? process.env.MEMO_STACK_OBSIDIAN_VERSION ?? readMacAppVersion(defaultMacObsidianApp)
  : undefined;

export const config: WebdriverIO.Config = {
  runner: "local",
  framework: "mocha",
  specs: ["./test/specs/**/*.e2e.ts"],
  maxInstances: 1,

  capabilities: [
    {
      browserName: "obsidian",
      browserVersion: localObsidianVersion ?? "latest",
      "wdio:obsidianOptions": {
        installerVersion: localObsidianVersion ?? "latest",
        ...(hasLocalObsidian
          ? {
              appVersion: localObsidianVersion,
              binaryPath: localBinaryPath,
              appPath: localAppPath,
            }
          : {}),
        plugins: ["."],
        vault: "test/vaults/simple",
        copy: true,
      },
      "goog:chromeOptions": {
        args: [
          "--window-position=-32000,-32000",
          "--window-size=1200,900",
        ],
      },
    },
  ],

  services: ["obsidian"],
  reporters: ["obsidian"],
  cacheDir: path.resolve(rootDir, ".obsidian-cache"),
  logLevel: "warn",

  mochaOpts: {
    ui: "bdd",
    timeout: 120000,
  },

  onPrepare() {
    fs.chmodSync(fakeCliPath, 0o755);
    fs.chmodSync(realCliPath, 0o755);
  },
};
