# Memo Stack Obsidian Plugin

Thin desktop plugin for controlling the local Memo Stack Obsidian connector.

The plugin intentionally does not parse, merge or mutate Memo Stack notes itself.
It delegates sync behavior to `memo-stack-obsidian`, keeping conflict handling,
idempotency and note format policy in the Python connector.

## Install

Recommended local install:

```bash
memo-stack-obsidian install-plugin \
  --vault "<vault>" \
  --enable \
  --space default \
  --memory_scope default \
  --local-cli-path memo-stack \
  --root-folder "Memo Stack" \
  --layout v2
```

Then open Obsidian. The plugin settings are prefilled with the vault path,
project, memory_scope, root folder and default local API URL.

Vaults with a non-default Obsidian config folder can use
`memo-stack-obsidian install-plugin --obsidian-config-dir <relative-dir>` or
`MEMORY_MCP_OBSIDIAN_CONFIG_DIR=<relative-dir>` through MCP. The path must stay
inside the vault.

Open the Memo Stack sidebar panel from the ribbon or command palette:

```text
Memo Stack: Open control center
```

The panel shows the current vault path, root folder, project, memory_scope, scoped
Generated/Inbox/Conflicts paths, a five-step setup checklist, local stack
controls, and vault sync controls. Opening the panel does not start the backend,
run the connector, or mutate notes.

`Prepare` runs the safe first-use flow: initialize local config, connect the
vault folders, check local stack status, and run Preview only when the API is
already reachable. It does not start Docker and does not run Sync.

`Init` runs `memo-stack init --api-url <current API URL> --json` explicitly and
does not start Docker or the Memo Stack server.

`Start lite` has a short cooldown after a successful start request, and plugin
buttons are disabled while a CLI command is already running.

By default, notes are grouped inside the vault:

```text
Memo Stack/
  spaces/<project>/memory_scopes/<memory_scope>/generated/facts/
  spaces/<project>/memory_scopes/<memory_scope>/inbox/
  spaces/<project>/memory_scopes/<memory_scope>/conflicts/
```

The legacy flat layout is still readable with `--layout v1`.

Manual source install:

```bash
cd packages/memo_stack_obsidian_plugin
npm install
npm run build
mkdir -p "<vault>/.obsidian/plugins/memo-stack"
cp manifest.json main.js styles.css "<vault>/.obsidian/plugins/memo-stack/"
```

## Required Local Setup

The Python connector must be installed and available on PATH:

```bash
memo-stack-obsidian --help
```

If it is installed elsewhere, set `Connector CLI path` in plugin settings.
For local stack controls, `memo-stack` must also be available on PATH. If it is
installed elsewhere, set `Local CLI path`.

Useful command palette actions:

```text
Memo Stack: Open control center
Memo Stack: Prepare this vault
Memo Stack: Initialize local stack config
Memo Stack: Check local stack status
Memo Stack: Start local stack lite
Memo Stack: Run doctor
Memo Stack: Connect this vault
Memo Stack: Preview sync
Memo Stack: Sync now
Memo Stack: Open Memo Stack inbox
Memo Stack: Open Memo Stack conflicts
```

## Tests

Typecheck and build:

```bash
npm run typecheck
npm run build
```

Run the Obsidian runtime E2E smoke:

```bash
MEMO_STACK_RUN_OBSIDIAN_E2E=1 npm run test:e2e:obsidian
```

This launches Obsidian through `wdio-obsidian-service`, loads the plugin in a
disposable vault, executes Memo Stack commands through Obsidian's command
registry, and verifies that the plugin delegates to the connector CLI.

Without `MEMO_STACK_RUN_OBSIDIAN_E2E=1`, the command exits after printing a
skip message because Obsidian is a real desktop app and can take focus.

## Agent Setup Through MCP

Local Memo Stack runtime tools are off by default. Enable them explicitly when
you want an MCP agent to prepare or diagnose the local backend:

```bash
export MEMORY_MCP_LOCAL_RUNTIME_ENABLED=true
export MEMORY_MCP_LOCAL_RUNTIME_HOME="$HOME/.memo-stack"
export MEMORY_MCP_LOCAL_RUNTIME_REPO_DIR="<memo-stack repo>"
```

This exposes `memory_local_runtime_status`, `memory_local_runtime_init`,
`memory_local_runtime_doctor` and dry-run `memory_local_runtime_start`. A real
Docker start has a separate gate:

```bash
export MEMORY_MCP_LOCAL_RUNTIME_START_ENABLED=true
```

MCP Obsidian tools are off by default. Enable them explicitly:

```bash
export MEMORY_MCP_OBSIDIAN_ENABLED=true
export MEMORY_MCP_OBSIDIAN_VAULT="<vault>"
```

Mutating sync has a separate gate:

```bash
export MEMORY_MCP_OBSIDIAN_SYNC_ENABLED=true
```

Agents can call `memory_obsidian_prepare` for the safe first-use flow. Dry-run
is the default. With `apply=true` it initializes local config, writes vault
folders, installs/enables the bundled plugin, checks backend status, and runs
Preview only when the API is already reachable. It does not start Docker, launch
Obsidian, or run Sync.

Non-UI MCP smoke from the repository root:

```bash
python scripts/obsidian_mcp_smoke.py
```

It starts the real MCP server over stdio, verifies local runtime and Obsidian
tools are listed, dry-runs setup, applies local config and V2 vault setup with
plugin install/enable, and checks that mutating sync/start are still blocked
unless their separate env gates are enabled.
