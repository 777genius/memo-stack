from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "memory-agent-plugin"
PLUGIN_KIT = PROJECT_ROOT / "scripts" / "plugin-kit-ai-local"
INTEGRATION_ID = "memory-agent-plugin"
INSTALL_TARGETS = ("codex", "claude", "gemini", "opencode", "cursor")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install or update the Memory Agent plugin.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if is_managed():
        command = [str(PLUGIN_KIT), "update", INTEGRATION_ID]
        action = "update"
    else:
        command = [str(PLUGIN_KIT), "add", str(PLUGIN_ROOT)]
        for target in INSTALL_TARGETS:
            command.extend(["--target", target])
        action = "add"

    if args.dry_run:
        command.append("--dry-run")

    print(f"memory-agent-plugin {action}: {' '.join(command)}", file=sys.stderr)
    return subprocess.call(command, cwd=PROJECT_ROOT)


def is_managed() -> bool:
    state_path = Path(
        os.getenv("PLUGIN_KIT_AI_STATE_PATH", str(Path.home() / ".plugin-kit-ai" / "state.json"))
    )
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    installations = state.get("installations")
    if not isinstance(installations, list):
        return False
    return any(
        isinstance(item, dict) and item.get("integration_id") == INTEGRATION_ID
        for item in installations
    )


if __name__ == "__main__":
    raise SystemExit(main())
