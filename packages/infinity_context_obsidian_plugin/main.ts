import {
  App,
  Notice,
  Platform,
  Plugin,
  PluginSettingTab,
  Setting,
  TFile,
  normalizePath,
  requestUrl,
} from "obsidian";
import type { ExecFileException, ExecFileOptionsWithStringEncoding } from "child_process";
import {
  type ConnectorCommand,
  type ConnectorRunResult,
  type LocalStackCommand,
  type InfinityContextPathPlan,
  type InfinityContextSnapshot,
  defaultLayoutPaths,
  errorMessage,
  exitCode,
  joinUrl,
  localStackApiReady,
  localStackArgs,
  parseJson,
  sanitizeRunResult,
  safeRootFolder,
  safeScopeSegment,
  summarizeLocalStackResult,
  summarizeResult,
} from "./support";
import { InfinityContextControlView } from "./panel";

interface InfinityContextSettings {
  apiUrl: string;
  token: string;
  localCliPath: string;
  cliPath: string;
  vaultPathOverride: string;
  rootFolder: string;
  layoutVersion: "v1" | "v2";
  spaceSlug: string;
  memoryScopeExternalRef: string;
  applyImportOnSync: boolean;
  commandTimeoutMs: number;
}

const DEFAULT_SETTINGS: InfinityContextSettings = {
  apiUrl: "http://127.0.0.1:7788",
  token: "",
  localCliPath: "infinity-context",
  cliPath: "infinity-context-obsidian",
  vaultPathOverride: "",
  rootFolder: "Infinity Context",
  layoutVersion: "v2",
  spaceSlug: "default",
  memoryScopeExternalRef: "default",
  applyImportOnSync: false,
  commandTimeoutMs: 30000,
};

const VIEW_TYPE_INFINITY_CONTEXT = "infinity-context-control-center";
const START_LITE_COOLDOWN_MS = 30000;

function normalizeSettings(value: unknown): InfinityContextSettings {
  const data = isRecord(value) ? value : {};
  return {
    apiUrl: stringSetting(data, "apiUrl", DEFAULT_SETTINGS.apiUrl),
    token: stringSetting(data, "token", DEFAULT_SETTINGS.token),
    localCliPath: stringSetting(data, "localCliPath", DEFAULT_SETTINGS.localCliPath),
    cliPath: stringSetting(data, "cliPath", DEFAULT_SETTINGS.cliPath),
    vaultPathOverride: stringSetting(
      data,
      "vaultPathOverride",
      DEFAULT_SETTINGS.vaultPathOverride,
    ),
    rootFolder: stringSetting(data, "rootFolder", DEFAULT_SETTINGS.rootFolder),
    layoutVersion: layoutVersionSetting(data.layoutVersion),
    spaceSlug: stringSetting(data, "spaceSlug", DEFAULT_SETTINGS.spaceSlug),
    memoryScopeExternalRef: stringSetting(
      data,
      "memoryScopeExternalRef",
      DEFAULT_SETTINGS.memoryScopeExternalRef,
    ),
    applyImportOnSync:
      typeof data.applyImportOnSync === "boolean"
        ? data.applyImportOnSync
        : DEFAULT_SETTINGS.applyImportOnSync,
    commandTimeoutMs: timeoutSetting(data.commandTimeoutMs),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function stringSetting(
  data: Record<string, unknown>,
  key: keyof InfinityContextSettings,
  fallback: string,
): string {
  const value = data[key];
  return typeof value === "string" ? value : fallback;
}

function layoutVersionSetting(value: unknown): "v1" | "v2" {
  return value === "v1" || value === "v2" ? value : DEFAULT_SETTINGS.layoutVersion;
}

function timeoutSetting(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value > 0
    ? value
    : DEFAULT_SETTINGS.commandTimeoutMs;
}

function markSettingInput(inputEl: HTMLInputElement, name: string): void {
  inputEl.dataset.infinityContextSetting = name;
}

export default class InfinityContextPlugin extends Plugin {
  settings: InfinityContextSettings = { ...DEFAULT_SETTINGS };
  private lastResult: ConnectorRunResult | null = null;
  private lastStackResult: ConnectorRunResult | null = null;
  private lastCommand: ConnectorCommand | null = null;
  private lastStackCommand: LocalStackCommand | null = null;
  private busyLabel = "";
  private lastStartLiteAt = 0;

  async onload() {
    await this.loadSettings();

    this.registerView(
      VIEW_TYPE_INFINITY_CONTEXT,
      (leaf) => new InfinityContextControlView(leaf, this, VIEW_TYPE_INFINITY_CONTEXT),
    );

    this.addRibbonIcon("database", "Infinity Context", () => {
      void this.openControlCenter();
    });

    this.addCommand({
      id: "open-control-center",
      name: "Open control center",
      callback: async () => {
        await this.openControlCenter();
      },
    });

    this.addCommand({
      id: "check-daemon-health",
      name: "Check daemon health",
      callback: async () => {
        await this.checkDaemonHealth();
      },
    });

    this.addCommand({
      id: "run-doctor",
      name: "Run doctor",
      callback: async () => {
        await this.runDoctor();
      },
    });

    this.addCommand({
      id: "local-stack-init",
      name: "Initialize local stack config",
      callback: async () => {
        await this.initLocalStack();
      },
    });

    this.addCommand({
      id: "local-stack-status",
      name: "Check local stack status",
      callback: async () => {
        await this.checkLocalStackStatus();
      },
    });

    this.addCommand({
      id: "local-stack-doctor",
      name: "Run local stack doctor",
      callback: async () => {
        await this.runLocalStackDoctor();
      },
    });

    this.addCommand({
      id: "start-local-stack-lite",
      name: "Start local stack lite",
      callback: async () => {
        await this.startLocalStackLite();
      },
    });

    this.addCommand({
      id: "prepare-vault",
      name: "Prepare this vault",
      callback: async () => {
        await this.prepareVault();
      },
    });

    this.addCommand({
      id: "connect-vault",
      name: "Connect this vault",
      callback: async () => {
        await this.connectVault();
      },
    });

    this.addCommand({
      id: "preview-sync",
      name: "Preview sync",
      callback: async () => {
        await this.previewSync();
      },
    });

    this.addCommand({
      id: "sync-now",
      name: "Sync now",
      callback: async () => {
        await this.syncNow();
      },
    });

    this.addCommand({
      id: "open-infinity-context-readme",
      name: "Open Infinity Context README",
      callback: async () => {
        await this.openInfinityContextReadme();
      },
    });

    this.addCommand({
      id: "open-inbox",
      name: "Open Infinity Context inbox",
      callback: async () => {
        await this.openInbox();
      },
    });

    this.addCommand({
      id: "open-conflicts",
      name: "Open Infinity Context conflicts",
      callback: async () => {
        await this.openConflicts();
      },
    });

    this.addSettingTab(new InfinityContextSettingTab(this.app, this));
  }

  async onunload() {
    this.app.workspace.detachLeavesOfType(VIEW_TYPE_INFINITY_CONTEXT);
  }

  async loadSettings() {
    try {
      this.settings = normalizeSettings(await this.loadData());
    } catch (error) {
      console.warn("Infinity Context settings could not be loaded; using defaults.", error);
      this.settings = { ...DEFAULT_SETTINGS };
    }
  }

  async saveSettings() {
    await this.saveData(this.settings);
  }

  async checkDaemonHealth() {
    try {
      const response = await requestUrl({
        url: joinUrl(this.settings.apiUrl, "/v1/health"),
        method: "GET",
        headers: this.authHeaders(),
      });
      if (response.status < 200 || response.status >= 300) {
        throw new Error(`HTTP ${response.status}`);
      }
      new Notice("Infinity Context daemon is healthy.");
    } catch (error) {
      new Notice(`Infinity Context health check failed: ${errorMessage(error)}`, 10000);
    }
  }

  async checkLocalStackStatus() {
    await this.runLocalStackAndReport("status");
  }

  async initLocalStack() {
    await this.runLocalStackAndReport("init");
  }

  async runLocalStackDoctor() {
    await this.runLocalStackAndReport("doctor");
  }

  async startLocalStackLite() {
    const cooldownSeconds = this.startLiteCooldownSeconds();
    if (cooldownSeconds > 0) {
      new Notice(`Infinity Context start was just requested. Try again in ${cooldownSeconds}s.`);
      this.refreshControlViews();
      return;
    }
    await this.runLocalStackAndReport("start-lite");
  }

  async openControlCenter() {
    const { workspace } = this.app;
    const leaves = workspace.getLeavesOfType(VIEW_TYPE_INFINITY_CONTEXT);
    const leaf = leaves[0] ?? workspace.getRightLeaf(false);
    if (!leaf) {
      new Notice("Could not open Infinity Context panel.");
      return;
    }
    await leaf.setViewState({ type: VIEW_TYPE_INFINITY_CONTEXT, active: true });
    workspace.revealLeaf(leaf);
  }

  async connectVault() {
    await this.runAndReport("connect");
  }

  async prepareVault() {
    if (this.busyLabel) {
      new Notice(`Infinity Context is already running: ${this.busyLabel}`);
      return;
    }
    try {
      this.layoutPaths();
      this.busyLabel = "preparing vault";
      this.refreshControlViews();

      const init = await this.runPreparedLocalStep("init");
      if (init.exitCode !== 0) {
        new Notice("Infinity Context prepare stopped: local config was not initialized.", 12000);
        return;
      }

      const connect = await this.runPreparedConnectorStep("connect");
      if (connect.exitCode !== 0) {
        new Notice("Infinity Context prepare stopped: vault was not connected.", 12000);
        return;
      }

      const status = await this.runPreparedLocalStep("status");
      if (status.exitCode !== 0 || !localStackApiReady(status)) {
        new Notice("Infinity Context prepared. Start lite, then run Preview.", 10000);
        return;
      }

      const preview = await this.runPreparedConnectorStep("preview");
      new Notice(
        preview.exitCode === 0
          ? "Infinity Context prepared and preview checked."
          : "Infinity Context prepared, but preview needs attention.",
        preview.exitCode === 0 ? 8000 : 12000,
      );
    } catch (error) {
      new Notice(`Infinity Context prepare failed: ${errorMessage(error)}`, 12000);
    } finally {
      this.busyLabel = "";
      this.refreshControlViews();
    }
  }

  async runDoctor() {
    await this.runAndReport("doctor");
  }

  async previewSync() {
    await this.runAndReport("preview");
  }

  async syncNow() {
    await this.runAndReport("sync");
  }

  async openInfinityContextReadme() {
    await this.openVaultFile(this.layoutPaths().readme, "Infinity Context README");
  }

  async openInbox() {
    await this.openVaultFile(
      normalizePath(`${this.layoutPaths().inbox}/README.md`),
      "Infinity Context inbox",
    );
  }

  async openConflicts() {
    await this.openVaultFile(
      normalizePath(`${this.layoutPaths().conflicts}/README.md`),
      "Infinity Context conflicts",
    );
  }

  private async openVaultFile(path: string, label: string) {
    const file = this.app.vault.getAbstractFileByPath(path);
    if (!(file instanceof TFile)) {
      new Notice(`${label} not found. Run Connect this vault first.`);
      return;
    }
    await this.app.workspace.getLeaf(false).openFile(file);
  }

  snapshot(): InfinityContextSnapshot {
    let pathError = "";
    let paths: InfinityContextPathPlan;
    try {
      paths = this.layoutPaths();
    } catch (error) {
      pathError = errorMessage(error);
      paths = defaultLayoutPaths(DEFAULT_SETTINGS);
    }
    return {
      desktop: Platform.isDesktopApp,
      vaultPath: this.safeVaultPath(),
      apiUrl: this.settings.apiUrl.trim() || DEFAULT_SETTINGS.apiUrl,
      rootFolder: this.settings.rootFolder.trim() || DEFAULT_SETTINGS.rootFolder,
      layoutVersion: this.settings.layoutVersion || DEFAULT_SETTINGS.layoutVersion,
      spaceSlug: this.settings.spaceSlug.trim() || DEFAULT_SETTINGS.spaceSlug,
      memoryScopeExternalRef:
        this.settings.memoryScopeExternalRef.trim() || DEFAULT_SETTINGS.memoryScopeExternalRef,
      paths,
      readmeExists: this.exists(paths.readme),
      generatedFactsExists: this.exists(paths.generatedFacts),
      inboxExists: this.exists(paths.inbox),
      conflictsExists: this.exists(paths.conflicts),
      pathError,
      busyLabel: this.busyLabel,
      startLiteCooldownSeconds: this.startLiteCooldownSeconds(),
      lastCommand: this.lastCommand,
      lastStackCommand: this.lastStackCommand,
      lastResult: this.lastResult,
      lastStackResult: this.lastStackResult,
    };
  }

  private async runAndReport(command: ConnectorCommand) {
    if (this.busyLabel) {
      new Notice(`Infinity Context is already running: ${this.busyLabel}`);
      return;
    }
    try {
      this.layoutPaths();
      this.busyLabel = connectorBusyLabel(command);
      this.refreshControlViews();
      const result = await this.runConnector(command);
      this.lastCommand = command;
      this.lastResult = result;
      const message = summarizeResult(command, result);
      new Notice(message, result.exitCode === 0 ? 8000 : 12000);
      if (result.exitCode !== 0) {
        console.warn("Infinity Context connector exited with non-zero status", result);
      }
    } catch (error) {
      new Notice(`Infinity Context ${command} failed: ${errorMessage(error)}`, 12000);
    } finally {
      this.busyLabel = "";
      this.refreshControlViewsAfterVaultWrite();
    }
  }

  private async runLocalStackAndReport(command: LocalStackCommand) {
    if (this.busyLabel) {
      new Notice(`Infinity Context is already running: ${this.busyLabel}`);
      return;
    }
    try {
      this.busyLabel = localStackBusyLabel(command);
      this.refreshControlViews();
      const result = await this.runLocalStack(command);
      this.lastStackCommand = command;
      this.lastStackResult = result;
      if (command === "start-lite" && result.exitCode === 0) {
        this.lastStartLiteAt = Date.now();
      }
      const message = summarizeLocalStackResult(command, result);
      new Notice(message, result.exitCode === 0 ? 8000 : 12000);
      if (result.exitCode !== 0) {
        console.warn("Infinity Context local stack command exited with non-zero status", result);
      }
    } catch (error) {
      new Notice(`Infinity Context local ${command} failed: ${errorMessage(error)}`, 12000);
    } finally {
      this.busyLabel = "";
      this.refreshControlViews();
    }
  }

  private async runPreparedConnectorStep(
    command: Extract<ConnectorCommand, "connect" | "preview">,
  ): Promise<ConnectorRunResult> {
    const result = await this.runConnector(command);
    this.lastCommand = command;
    this.lastResult = result;
    if (result.exitCode !== 0) {
      console.warn("Infinity Context prepare connector step failed", command, result);
    }
    return result;
  }

  private async runPreparedLocalStep(
    command: Extract<LocalStackCommand, "init" | "status">,
  ): Promise<ConnectorRunResult> {
    const result = await this.runLocalStack(command);
    this.lastStackCommand = command;
    this.lastStackResult = result;
    if (result.exitCode !== 0) {
      console.warn("Infinity Context prepare local step failed", command, result);
    }
    return result;
  }

  private async runConnector(command: ConnectorCommand): Promise<ConnectorRunResult> {
    if (!Platform.isDesktopApp) {
      throw new Error("The Infinity Context plugin currently requires desktop Obsidian.");
    }

    const vaultPath = this.resolveVaultPath();
    const args = this.connectorArgs(command, vaultPath);
    const childProcess = require("child_process") as typeof import("child_process");
    const options: ExecFileOptionsWithStringEncoding = {
      cwd: vaultPath,
      encoding: "utf8",
      env: this.connectorEnv(),
      timeout: Math.max(this.settings.commandTimeoutMs, 1000),
      windowsHide: true,
      maxBuffer: 1024 * 1024,
    };

    return await new Promise((resolve) => {
      childProcess.execFile(
        this.settings.cliPath,
        args,
        options,
        (error: ExecFileException | null, stdout: string, stderr: string) => {
          resolve(
            sanitizeRunResult({
              exitCode: exitCode(error),
              stdout,
              stderr,
              payload: parseJson(stdout),
            }),
          );
        },
      );
    });
  }

  private async runLocalStack(command: LocalStackCommand): Promise<ConnectorRunResult> {
    if (!Platform.isDesktopApp) {
      throw new Error("The Infinity Context plugin currently requires desktop Obsidian.");
    }

    const apiUrl = this.settings.apiUrl.trim() || DEFAULT_SETTINGS.apiUrl;
    const args = localStackArgs(command, apiUrl);
    const childProcess = require("child_process") as typeof import("child_process");
    const options: ExecFileOptionsWithStringEncoding = {
      encoding: "utf8",
      env: this.localStackEnv(),
      timeout: Math.max(this.settings.commandTimeoutMs, 1000),
      windowsHide: true,
      maxBuffer: 1024 * 1024,
    };
    const cwd = this.safeVaultPath();
    if (cwd) {
      options.cwd = cwd;
    }

    return await new Promise((resolve) => {
      childProcess.execFile(
        this.settings.localCliPath || DEFAULT_SETTINGS.localCliPath,
        args,
        options,
        (error: ExecFileException | null, stdout: string, stderr: string) => {
          resolve(
            sanitizeRunResult({
              exitCode: exitCode(error),
              stdout,
              stderr,
              payload: parseJson(stdout),
            }),
          );
        },
      );
    });
  }

  private connectorArgs(command: ConnectorCommand, vaultPath: string): string[] {
    const args = [
      command,
      "--vault",
      vaultPath,
      "--space",
      this.settings.spaceSlug.trim() || DEFAULT_SETTINGS.spaceSlug,
      "--memory_scope",
      this.settings.memoryScopeExternalRef.trim() || DEFAULT_SETTINGS.memoryScopeExternalRef,
      "--root-folder",
      this.settings.rootFolder.trim() || DEFAULT_SETTINGS.rootFolder,
      "--layout",
      this.settings.layoutVersion || DEFAULT_SETTINGS.layoutVersion,
      "--api-url",
      this.settings.apiUrl.trim() || DEFAULT_SETTINGS.apiUrl,
      "--json",
    ];
    if (command === "sync" && this.settings.applyImportOnSync) {
      args.push("--apply-import");
    }
    return args;
  }

  private connectorEnv(): NodeJS.ProcessEnv {
    const env = { ...process.env };
    const apiUrl = this.settings.apiUrl.trim() || DEFAULT_SETTINGS.apiUrl;
    env.MEMORY_API_URL = apiUrl;
    env.MEMORY_MCP_API_URL = apiUrl;
    const token = this.settings.token.trim();
    if (token) {
      env.MEMORY_SERVICE_TOKEN = token;
      env.MEMORY_MCP_AUTH_TOKEN = token;
    }
    return env;
  }

  private localStackEnv(): NodeJS.ProcessEnv {
    const env = this.connectorEnv();
    const vaultPath = this.safeVaultPath();
    if (vaultPath) {
      env.INFINITY_CONTEXT_OBSIDIAN_VAULT = vaultPath;
    }
    return env;
  }

  private authHeaders(): Record<string, string> {
    const headers: Record<string, string> = { Accept: "application/json" };
    const token = this.settings.token.trim();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    return headers;
  }

  private resolveVaultPath(): string {
    const override = this.settings.vaultPathOverride.trim();
    if (override) {
      return override;
    }
    const adapter = this.app.vault.adapter as { basePath?: string };
    if (adapter.basePath) {
      return adapter.basePath;
    }
    throw new Error("Vault path is unavailable. Set Vault path override in settings.");
  }

  private safeVaultPath(): string {
    try {
      return this.resolveVaultPath();
    } catch (_error) {
      return "";
    }
  }

  private layoutPaths(): InfinityContextPathPlan {
    const root = safeRootFolder(this.settings.rootFolder || DEFAULT_SETTINGS.rootFolder);
    if ((this.settings.layoutVersion || DEFAULT_SETTINGS.layoutVersion) === "v1") {
      return {
        root,
        readme: normalizePath(`${root}/README.md`),
        generatedFacts: normalizePath(`${root}/generated/facts`),
        inbox: normalizePath(`${root}/inbox`),
        conflicts: normalizePath(`${root}/conflicts`),
      };
    }
    const space = safeScopeSegment(
      this.settings.spaceSlug || DEFAULT_SETTINGS.spaceSlug,
      DEFAULT_SETTINGS.spaceSlug,
    );
    const memory_scope = safeScopeSegment(
      this.settings.memoryScopeExternalRef || DEFAULT_SETTINGS.memoryScopeExternalRef,
      DEFAULT_SETTINGS.memoryScopeExternalRef,
    );
    const scope = normalizePath(`${root}/spaces/${space}/memory_scopes/${memory_scope}`);
    return {
      root,
      readme: normalizePath(`${root}/README.md`),
      generatedFacts: normalizePath(`${scope}/generated/facts`),
      inbox: normalizePath(`${scope}/inbox`),
      conflicts: normalizePath(`${scope}/conflicts`),
    };
  }

  private exists(path: string): boolean {
    return this.app.vault.getAbstractFileByPath(path) !== null;
  }

  private refreshControlViews() {
    for (const leaf of this.app.workspace.getLeavesOfType(VIEW_TYPE_INFINITY_CONTEXT)) {
      if (leaf.view instanceof InfinityContextControlView) {
        leaf.view.render();
      }
    }
  }

  private refreshControlViewsAfterVaultWrite() {
    this.refreshControlViews();
    for (const delayMs of [250, 1000, 2500]) {
      setTimeout(() => this.refreshControlViews(), delayMs);
    }
  }

  private startLiteCooldownSeconds(): number {
    const remaining = START_LITE_COOLDOWN_MS - (Date.now() - this.lastStartLiteAt);
    return remaining > 0 ? Math.ceil(remaining / 1000) : 0;
  }
}

class InfinityContextSettingTab extends PluginSettingTab {
  plugin: InfinityContextPlugin;

  constructor(app: App, plugin: InfinityContextPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.createEl("h2", { text: "Infinity Context" });

    if (!Platform.isDesktopApp) {
      containerEl.createEl("p", {
        text: "This plugin currently requires desktop Obsidian.",
        cls: "infinity-context-settings-warning",
      });
    }

    new Setting(containerEl)
      .setName("API URL")
      .setDesc("Local Infinity Context server URL.")
      .addText((text) => {
        markSettingInput(text.inputEl, "apiUrl");
        text
          .setPlaceholder(DEFAULT_SETTINGS.apiUrl)
          .setValue(this.plugin.settings.apiUrl)
          .onChange(async (value) => {
            this.plugin.settings.apiUrl = value.trim();
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName("Service token")
      .setDesc("Stored in Obsidian plugin data and passed to the CLI through env.")
      .addText((text) => {
        text.inputEl.type = "password";
        markSettingInput(text.inputEl, "token");
        text
          .setPlaceholder("optional")
          .setValue(this.plugin.settings.token)
          .onChange(async (value) => {
            this.plugin.settings.token = value.trim();
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName("Local CLI path")
      .setDesc("Use an absolute path if Obsidian does not inherit your shell PATH.")
      .addText((text) => {
        markSettingInput(text.inputEl, "localCliPath");
        text
          .setPlaceholder(DEFAULT_SETTINGS.localCliPath)
          .setValue(this.plugin.settings.localCliPath)
          .onChange(async (value) => {
            this.plugin.settings.localCliPath =
              value.trim() || DEFAULT_SETTINGS.localCliPath;
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName("Connector CLI path")
      .setDesc("Use an absolute path if Obsidian does not inherit your shell PATH.")
      .addText((text) => {
        markSettingInput(text.inputEl, "cliPath");
        text
          .setPlaceholder(DEFAULT_SETTINGS.cliPath)
          .setValue(this.plugin.settings.cliPath)
          .onChange(async (value) => {
            this.plugin.settings.cliPath = value.trim() || DEFAULT_SETTINGS.cliPath;
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName("Vault path override")
      .setDesc("Optional. Leave empty to use the current desktop vault path.")
      .addText((text) => {
        markSettingInput(text.inputEl, "vaultPathOverride");
        text
          .setPlaceholder("/Users/me/Notes")
          .setValue(this.plugin.settings.vaultPathOverride)
          .onChange(async (value) => {
            this.plugin.settings.vaultPathOverride = value.trim();
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName("Folder")
      .setDesc("Root folder inside the vault where Infinity Context writes project memory.")
      .addText((text) => {
        markSettingInput(text.inputEl, "rootFolder");
        text
          .setPlaceholder(DEFAULT_SETTINGS.rootFolder)
          .setValue(this.plugin.settings.rootFolder)
          .onChange(async (value) => {
            this.plugin.settings.rootFolder = value.trim() || DEFAULT_SETTINGS.rootFolder;
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName("Layout")
      .setDesc("v2 groups notes by project and memory_scope. v1 reads the legacy flat layout.")
      .addDropdown((dropdown) =>
        dropdown
          .addOption("v2", "Project folders")
          .addOption("v1", "Legacy flat")
          .setValue(this.plugin.settings.layoutVersion || DEFAULT_SETTINGS.layoutVersion)
          .onChange(async (value) => {
            this.plugin.settings.layoutVersion = value === "v1" ? "v1" : "v2";
            await this.plugin.saveSettings();
          }),
      );

    new Setting(containerEl)
      .setName("Project")
      .addText((text) => {
        markSettingInput(text.inputEl, "spaceSlug");
        text
          .setPlaceholder(DEFAULT_SETTINGS.spaceSlug)
          .setValue(this.plugin.settings.spaceSlug)
          .onChange(async (value) => {
            this.plugin.settings.spaceSlug = value.trim() || DEFAULT_SETTINGS.spaceSlug;
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName("MemoryScope")
      .addText((text) => {
        markSettingInput(text.inputEl, "memoryScopeExternalRef");
        text
          .setPlaceholder(DEFAULT_SETTINGS.memoryScopeExternalRef)
          .setValue(this.plugin.settings.memoryScopeExternalRef)
          .onChange(async (value) => {
            this.plugin.settings.memoryScopeExternalRef =
              value.trim() || DEFAULT_SETTINGS.memoryScopeExternalRef;
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName("Apply imports on sync")
      .setDesc("When disabled, Sync now reports direct note edits without updating Infinity Context.")
      .addToggle((toggle) => {
        toggle.toggleEl.dataset.infinityContextSetting = "applyImportOnSync";
        toggle.setValue(this.plugin.settings.applyImportOnSync).onChange(async (value) => {
          this.plugin.settings.applyImportOnSync = value;
          await this.plugin.saveSettings();
        });
      });

    new Setting(containerEl)
      .setName("Command timeout")
      .setDesc("Milliseconds before the connector command is stopped.")
      .addText((text) => {
        markSettingInput(text.inputEl, "commandTimeoutMs");
        text
          .setPlaceholder(String(DEFAULT_SETTINGS.commandTimeoutMs))
          .setValue(String(this.plugin.settings.commandTimeoutMs))
          .onChange(async (value) => {
            const parsed = Number.parseInt(value, 10);
            this.plugin.settings.commandTimeoutMs = Number.isFinite(parsed)
              ? Math.max(parsed, 1000)
              : DEFAULT_SETTINGS.commandTimeoutMs;
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName("Local stack")
      .setDesc("Run explicit local stack commands from settings.")
      .addButton((button) =>
        button.setButtonText("Init").onClick(() => {
          void this.plugin.initLocalStack();
        }),
      )
      .addButton((button) =>
        button.setButtonText("Status").onClick(() => {
          void this.plugin.checkLocalStackStatus();
        }),
      )
      .addButton((button) =>
        button.setButtonText("Doctor").onClick(() => {
          void this.plugin.runLocalStackDoctor();
        }),
      )
      .addButton((button) =>
        button.setButtonText("Start lite").onClick(() => {
          void this.plugin.startLocalStackLite();
        }),
      );

    new Setting(containerEl)
      .setName("Vault sync")
      .setDesc("Run quick connector checks from settings.")
      .addButton((button) =>
        button.setButtonText("Prepare").onClick(() => {
          void this.plugin.prepareVault();
        }),
      )
      .addButton((button) =>
        button.setButtonText("Health").onClick(() => {
          void this.plugin.checkDaemonHealth();
        }),
      )
      .addButton((button) =>
        button.setButtonText("Doctor").onClick(() => {
          void this.plugin.runDoctor();
        }),
      )
      .addButton((button) =>
        button.setButtonText("Preview").onClick(() => {
          void this.plugin.previewSync();
        }),
      )
      .addButton((button) =>
        button.setButtonText("Sync").setCta().onClick(() => {
          void this.plugin.syncNow();
        }),
      );
  }
}

function connectorBusyLabel(command: ConnectorCommand): string {
  if (command === "connect") {
    return "connecting vault";
  }
  if (command === "doctor") {
    return "checking vault";
  }
  if (command === "preview") {
    return "previewing sync";
  }
  return "syncing vault";
}

function localStackBusyLabel(command: LocalStackCommand): string {
  if (command === "init") {
    return "initializing local config";
  }
  if (command === "status") {
    return "checking local stack";
  }
  if (command === "doctor") {
    return "running local doctor";
  }
  return "starting local stack";
}
