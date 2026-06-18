import { ItemView, WorkspaceLeaf } from "obsidian";
import {
  type ConnectorCommand,
  type ConnectorRunResult,
  type LocalStackCommand,
  type InfinityContextSnapshot,
  actionButton,
  asRecord,
  compactPayload,
  compactText,
  connected,
  connectedLabel,
  pathRow,
  statusRow,
} from "./support";

export interface InfinityContextPanelPlugin {
  snapshot(): InfinityContextSnapshot;
  checkDaemonHealth(): Promise<void>;
  initLocalStack(): Promise<void>;
  checkLocalStackStatus(): Promise<void>;
  runLocalStackDoctor(): Promise<void>;
  startLocalStackLite(): Promise<void>;
  prepareVault(): Promise<void>;
  runDoctor(): Promise<void>;
  connectVault(): Promise<void>;
  previewSync(): Promise<void>;
  syncNow(): Promise<void>;
  openInfinityContextReadme(): Promise<void>;
  openInbox(): Promise<void>;
  openConflicts(): Promise<void>;
}

export class InfinityContextControlView extends ItemView {
  private plugin: InfinityContextPanelPlugin;
  private viewType: string;

  constructor(leaf: WorkspaceLeaf, plugin: InfinityContextPanelPlugin, viewType: string) {
    super(leaf);
    this.plugin = plugin;
    this.viewType = viewType;
  }

  getViewType(): string {
    return this.viewType;
  }

  getDisplayText(): string {
    return "Infinity Context";
  }

  getIcon(): string {
    return "database";
  }

  async onOpen() {
    this.render();
  }

  render() {
    const snapshot = this.plugin.snapshot();
    const { contentEl } = this;
    contentEl.empty();
    contentEl.addClass("infinity-context-panel");

    contentEl.createEl("h2", { text: "Infinity Context" });

    const status = contentEl.createDiv({ cls: "infinity-context-status-grid" });
    statusRow(status, "Desktop", snapshot.desktop ? "Ready" : "Desktop required", snapshot.desktop);
    statusRow(status, "Vault", snapshot.vaultPath || "Set vault path override", Boolean(snapshot.vaultPath));
    statusRow(status, "Folder", snapshot.pathError || snapshot.rootFolder, !snapshot.pathError);
    statusRow(status, "Project", snapshot.spaceSlug, true);
    statusRow(status, "MemoryScope", snapshot.memoryScopeExternalRef, true);
    statusRow(status, "Connected", connectedLabel(snapshot), connected(snapshot));

    contentEl.createEl("h3", { text: "Paths" });
    const pathList = contentEl.createDiv({ cls: "infinity-context-path-list" });
    pathRow(pathList, "Generated", snapshot.paths.generatedFacts, snapshot.generatedFactsExists);
    pathRow(pathList, "Inbox", snapshot.paths.inbox, snapshot.inboxExists);
    pathRow(pathList, "Conflicts", snapshot.paths.conflicts, snapshot.conflictsExists);

    renderSetupChecklist(contentEl, snapshot, this.plugin);
    renderLocalStackActions(contentEl, snapshot, this.plugin);
    renderVaultActions(contentEl, snapshot, this.plugin);
    renderLastVaultRun(contentEl, snapshot.lastCommand, snapshot.lastResult);
    renderLastStackRun(contentEl, snapshot.lastStackCommand, snapshot.lastStackResult);
  }
}

function renderLocalStackActions(
  container: HTMLElement,
  snapshot: InfinityContextSnapshot,
  plugin: InfinityContextPanelPlugin,
) {
  container.createEl("h3", { text: "Local stack" });
  const actions = container.createDiv({ cls: "infinity-context-action-grid" });
  actionButton(actions, "Init", () => void plugin.initLocalStack(), {
    disabled: Boolean(snapshot.busyLabel),
  });
  actionButton(actions, "Status", () => void plugin.checkLocalStackStatus(), {
    disabled: Boolean(snapshot.busyLabel),
  });
  actionButton(actions, "Doctor", () => void plugin.runLocalStackDoctor(), {
    disabled: Boolean(snapshot.busyLabel),
  });
  actionButton(
    actions,
    snapshot.startLiteCooldownSeconds > 0
      ? `Start lite ${snapshot.startLiteCooldownSeconds}s`
      : "Start lite",
    () => void plugin.startLocalStackLite(),
    {
      disabled: Boolean(snapshot.busyLabel) || snapshot.startLiteCooldownSeconds > 0,
      title:
        snapshot.startLiteCooldownSeconds > 0
          ? "Start was just requested"
          : undefined,
    },
  );
  actionButton(actions, "Health", () => void plugin.checkDaemonHealth(), {
    disabled: Boolean(snapshot.busyLabel),
  });
}

function renderVaultActions(
  container: HTMLElement,
  snapshot: InfinityContextSnapshot,
  plugin: InfinityContextPanelPlugin,
) {
  container.createEl("h3", { text: "Vault sync" });
  const actions = container.createDiv({ cls: "infinity-context-action-grid" });
  actions.addClass("infinity-context-vault-actions");
  actionButton(actions, "Doctor", () => void plugin.runDoctor(), {
    disabled: Boolean(snapshot.busyLabel),
  });
  actionButton(actions, "Connect", () => void plugin.connectVault(), {
    disabled: Boolean(snapshot.busyLabel) || Boolean(snapshot.pathError),
  });
  actionButton(actions, "Preview", () => void plugin.previewSync(), {
    disabled: Boolean(snapshot.busyLabel) || Boolean(snapshot.pathError),
  });
  actionButton(actions, "Sync", () => void plugin.syncNow(), {
    cta: true,
    disabled: Boolean(snapshot.busyLabel) || Boolean(snapshot.pathError),
  });
  actionButton(actions, "README", () => void plugin.openInfinityContextReadme(), {
    disabled: Boolean(snapshot.busyLabel) || !snapshot.readmeExists,
  });
  actionButton(actions, "Inbox", () => void plugin.openInbox(), {
    disabled: Boolean(snapshot.busyLabel) || !snapshot.inboxExists,
  });
  actionButton(actions, "Conflicts", () => void plugin.openConflicts(), {
    disabled: Boolean(snapshot.busyLabel) || !snapshot.conflictsExists,
  });
}

function renderLastVaultRun(
  container: HTMLElement,
  _command: ConnectorCommand | null,
  result: ConnectorRunResult | null,
) {
  if (!result) {
    return;
  }
  const last = container.createDiv({ cls: "infinity-context-last-run" });
  last.createSpan({
    text: result.exitCode === 0 ? "Last run: ok" : "Last run: failed",
    cls: result.exitCode === 0 ? "infinity-context-ok" : "infinity-context-bad",
  });
  const payload = asRecord(result.payload);
  if (payload) {
    last.createEl("pre", {
      text: JSON.stringify(compactPayload(payload), null, 2),
    });
  }
}

function renderLastStackRun(
  container: HTMLElement,
  _command: LocalStackCommand | null,
  result: ConnectorRunResult | null,
) {
  if (!result) {
    return;
  }
  const last = container.createDiv({ cls: "infinity-context-last-run" });
  last.createSpan({
    text: result.exitCode === 0 ? "Local stack: ok" : "Local stack: failed",
    cls: result.exitCode === 0 ? "infinity-context-ok" : "infinity-context-bad",
  });
  const payload = asRecord(result.payload);
  last.createEl("pre", {
    text: payload
      ? JSON.stringify(compactPayload(payload), null, 2)
      : compactText(result.stdout, result.stderr),
  });
}

function renderSetupChecklist(
  container: HTMLElement,
  snapshot: InfinityContextSnapshot,
  plugin: InfinityContextPanelPlugin,
) {
  container.createEl("h3", { text: "Setup" });
  const list = container.createDiv({ cls: "infinity-context-setup-list" });
  const primary = list.createDiv({ cls: "infinity-context-setup-primary" });
  actionButton(primary, "Prepare", () => void plugin.prepareVault(), {
    cta: true,
    disabled: Boolean(snapshot.busyLabel) || Boolean(snapshot.pathError),
  });
  setupStep(list, {
    index: "1",
    label: "Config",
    status: snapshot.lastStackCommand === "init" && snapshot.lastStackResult?.exitCode === 0
      ? "Ready"
      : "Init",
    ok: snapshot.lastStackCommand === "init" && snapshot.lastStackResult?.exitCode === 0,
    button: "Init",
    disabled: Boolean(snapshot.busyLabel),
    onClick: () => void plugin.initLocalStack(),
  });
  setupStep(list, {
    index: "2",
    label: "Stack",
    status: stackStepStatus(snapshot),
    ok: stackStepOk(snapshot),
    button: "Status",
    disabled: Boolean(snapshot.busyLabel),
    onClick: () => void plugin.checkLocalStackStatus(),
  });
  setupStep(list, {
    index: "3",
    label: "Vault",
    status: connected(snapshot) ? "Ready" : "Connect",
    ok: connected(snapshot),
    button: connected(snapshot) ? "Doctor" : "Connect",
    disabled: Boolean(snapshot.busyLabel) || Boolean(snapshot.pathError),
    onClick: () => {
      if (connected(snapshot)) {
        void plugin.runDoctor();
      } else {
        void plugin.connectVault();
      }
    },
  });
  setupStep(list, {
    index: "4",
    label: "Preview",
    status: snapshot.lastCommand === "preview" && snapshot.lastResult?.exitCode === 0
      ? "Checked"
      : "Pending",
    ok: snapshot.lastCommand === "preview" && snapshot.lastResult?.exitCode === 0,
    button: "Preview",
    disabled: Boolean(snapshot.busyLabel) || Boolean(snapshot.pathError),
    onClick: () => void plugin.previewSync(),
  });
  setupStep(list, {
    index: "5",
    label: "Sync",
    status: snapshot.lastCommand === "sync" && snapshot.lastResult?.exitCode === 0
      ? "Done"
      : "Ready",
    ok: snapshot.lastCommand === "sync" && snapshot.lastResult?.exitCode === 0,
    button: "Sync",
    disabled: Boolean(snapshot.busyLabel) || Boolean(snapshot.pathError),
    cta: true,
    onClick: () => void plugin.syncNow(),
  });
  if (snapshot.busyLabel) {
    list.createDiv({ text: `Running: ${snapshot.busyLabel}`, cls: "infinity-context-busy" });
  }
}

function setupStep(
  container: HTMLElement,
  options: {
    index: string;
    label: string;
    status: string;
    ok: boolean;
    button: string;
    disabled: boolean;
    cta?: boolean;
    onClick: () => void;
  },
) {
  const row = container.createDiv({ cls: "infinity-context-setup-row" });
  row.createSpan({ text: options.index, cls: "infinity-context-setup-index" });
  row.createSpan({ text: options.label, cls: "infinity-context-status-label" });
  row.createSpan({
    text: options.status,
    cls: options.ok ? "infinity-context-ok" : "infinity-context-muted",
  });
  actionButton(row, options.button, options.onClick, {
    cta: options.cta,
    disabled: options.disabled,
  });
}

function stackStepStatus(snapshot: InfinityContextSnapshot): string {
  if (snapshot.lastStackCommand === "status" && snapshot.lastStackResult?.exitCode === 0) {
    return "Ready";
  }
  if (snapshot.lastStackCommand === "start-lite" && snapshot.lastStackResult?.exitCode === 0) {
    return "Started";
  }
  if (snapshot.lastStackResult?.exitCode && snapshot.lastStackResult.exitCode !== 0) {
    return "Check failed";
  }
  return "Check";
}

function stackStepOk(snapshot: InfinityContextSnapshot): boolean {
  return (
    (snapshot.lastStackCommand === "status" || snapshot.lastStackCommand === "start-lite") &&
    snapshot.lastStackResult?.exitCode === 0
  );
}
