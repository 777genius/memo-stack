#!/usr/bin/env node

const { spawn, spawnSync } = require("node:child_process");

if (process.env.INFINITY_CONTEXT_RUN_OBSIDIAN_E2E !== "1") {
  console.log(
    [
      "Skipping Obsidian UI E2E.",
      "This test launches the real Obsidian desktop app and may take focus.",
      "Run explicitly with:",
      "  INFINITY_CONTEXT_RUN_OBSIDIAN_E2E=1 npm run test:e2e:obsidian",
    ].join("\n"),
  );
  process.exit(0);
}

function appleScriptString(value) {
  return String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function frontmostAppName() {
  const result = spawnSync(
    "osascript",
    ["-e", 'tell application "System Events" to name of first application process whose frontmost is true'],
    {
      encoding: "utf8",
      timeout: 3000,
    },
  );
  if (result.status !== 0) {
    return "";
  }
  return String(result.stdout).trim();
}

function startMacFocusGuard() {
  if (process.platform !== "darwin" || process.env.INFINITY_CONTEXT_OBSIDIAN_E2E_FOCUS_GUARD === "0") {
    return () => {};
  }

  const initialRefocusApp = appleScriptString(process.env.INFINITY_CONTEXT_OBSIDIAN_E2E_REFOCUS_APP || frontmostAppName());
  const script = [
    `set refocusApp to "${initialRefocusApp}"`,
    "repeat",
    '  tell application "System Events"',
    '    set frontApp to ""',
    "    try",
    '      set frontApp to name of first application process whose frontmost is true',
    "    end try",
    '    if frontApp is not "" and frontApp is not "Obsidian" then',
    "      set refocusApp to frontApp",
    "    end if",
    '    if frontApp is "Obsidian" then',
    '      if exists (application process "Obsidian") then',
    '        set visible of application process "Obsidian" to false',
    "      end if",
    '      if refocusApp is not "" and refocusApp is not "Obsidian" and exists (application process refocusApp) then',
    "        set frontmost of application process refocusApp to true",
    "      end if",
    "    end if",
    "  end tell",
    "  delay 0.05",
    "end repeat",
  ];
  const guard = spawn("osascript", script.flatMap((line) => ["-e", line]), {
    stdio: ["ignore", "ignore", "pipe"],
  });
  let stopped = false;
  let stderr = "";

  guard.stderr.on("data", (chunk) => {
    stderr += String(chunk);
  });
  guard.on("error", (error) => {
    if (!stopped) {
      console.warn(`[infinity-context] Obsidian focus guard failed: ${error.message}`);
    }
  });
  guard.on("exit", (code, signal) => {
    if (!stopped) {
      const reason = signal ? `signal ${signal}` : `exit code ${code}`;
      const detail = stderr.trim();
      console.warn(`[infinity-context] Obsidian focus guard stopped unexpectedly: ${reason}${detail ? `: ${detail}` : ""}`);
    }
  });

  console.log(
    [
      "[infinity-context] Obsidian focus guard active.",
      "Set INFINITY_CONTEXT_OBSIDIAN_E2E_REFOCUS_APP to pin focus to a specific app.",
      "Disable with INFINITY_CONTEXT_OBSIDIAN_E2E_FOCUS_GUARD=0.",
    ].join(" "),
  );
  return () => {
    stopped = true;
    guard.kill("SIGTERM");
    const killTimer = setTimeout(() => guard.kill("SIGKILL"), 1000);
    killTimer.unref();
  };
}

const npm = process.platform === "win32" ? "npm.cmd" : "npm";
const stopFocusGuard = startMacFocusGuard();
const passthroughArgs = process.argv.slice(2);
const npmArgs = [
  "run",
  "test:e2e:obsidian:run",
  ...(passthroughArgs.length > 0 ? ["--", ...passthroughArgs] : []),
];
const child = spawn(npm, npmArgs, {
  stdio: "inherit",
  env: process.env,
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    stopFocusGuard();
    child.kill(signal);
  });
}

child.on("exit", (code, signal) => {
  stopFocusGuard();
  if (signal) {
    process.exit(signal === "SIGINT" ? 130 : 143);
  }
  process.exit(code ?? 1);
});
