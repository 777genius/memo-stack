import { normalizePath } from "obsidian";
import type { ExecFileException } from "child_process";

export interface ConnectorRunResult {
  exitCode: number;
  stdout: string;
  stderr: string;
  payload: unknown;
}

export interface MemoStackPathPlan {
  root: string;
  readme: string;
  generatedFacts: string;
  inbox: string;
  conflicts: string;
}

export interface MemoStackSnapshot {
  desktop: boolean;
  vaultPath: string;
  apiUrl: string;
  rootFolder: string;
  layoutVersion: "v1" | "v2";
  spaceSlug: string;
  profileExternalRef: string;
  paths: MemoStackPathPlan;
  readmeExists: boolean;
  generatedFactsExists: boolean;
  inboxExists: boolean;
  conflictsExists: boolean;
  pathError: string;
  busyLabel: string;
  startLiteCooldownSeconds: number;
  lastCommand: ConnectorCommand | null;
  lastStackCommand: LocalStackCommand | null;
  lastResult: ConnectorRunResult | null;
  lastStackResult: ConnectorRunResult | null;
}

export interface DefaultLayoutSettings {
  rootFolder: string;
  spaceSlug: string;
  profileExternalRef: string;
}

export type ConnectorCommand = "connect" | "doctor" | "preview" | "sync";
export type LocalStackCommand = "doctor" | "init" | "start-lite" | "status";

interface ActionButtonOptions {
  cta?: boolean;
  disabled?: boolean;
  title?: string;
}

export function statusRow(
  container: HTMLElement,
  label: string,
  value: string,
  ok: boolean,
) {
  const row = container.createDiv({ cls: "memo-stack-status-row" });
  row.createSpan({ text: label, cls: "memo-stack-status-label" });
  row.createSpan({
    text: value,
    cls: ok ? "memo-stack-ok" : "memo-stack-bad",
  });
}

export function pathRow(
  container: HTMLElement,
  label: string,
  path: string,
  exists: boolean,
) {
  const row = container.createDiv({ cls: "memo-stack-path-row" });
  row.createSpan({
    text: exists ? "OK" : "Missing",
    cls: exists ? "memo-stack-ok" : "memo-stack-muted",
  });
  row.createSpan({ text: label, cls: "memo-stack-status-label" });
  row.createEl("code", { text: path });
}

export function actionButton(
  container: HTMLElement,
  text: string,
  onClick: () => void,
  options: boolean | ActionButtonOptions = false,
) {
  const resolved = typeof options === "boolean" ? { cta: options } : options;
  const button = container.createEl("button", {
    text,
    cls: resolved.cta ? "mod-cta" : undefined,
  });
  button.disabled = resolved.disabled === true;
  if (resolved.title) {
    button.title = resolved.title;
  }
  button.addEventListener("click", onClick);
}

export function connected(snapshot: MemoStackSnapshot): boolean {
  return (
    snapshot.readmeExists &&
    snapshot.generatedFactsExists &&
    snapshot.inboxExists &&
    snapshot.conflictsExists &&
    !snapshot.pathError
  );
}

export function connectedLabel(snapshot: MemoStackSnapshot): string {
  if (snapshot.pathError) {
    return "Invalid path";
  }
  return connected(snapshot) ? "Ready" : "Run Connect";
}

export function compactPayload(payload: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const key of [
    "ok",
    "applied",
    "applied_import",
    "export_skipped",
    "export_skipped_reason",
    "api_url",
    "health",
    "capabilities",
    "written",
    "skipped",
    "checks",
    "import",
    "export",
  ]) {
    if (key in payload) {
      result[key] = payload[key];
    }
  }
  return result;
}

export function compactText(stdout: string, stderr: string): string {
  const text = [stdout.trim(), stderr.trim()].filter(Boolean).join("\n");
  return text.length > 2000 ? `${text.slice(0, 2000)}...` : text;
}

export function localStackArgs(command: LocalStackCommand, apiUrl: string): string[] {
  if (command === "init") {
    return ["init", "--api-url", apiUrl, "--json"];
  }
  if (command === "status") {
    return ["status", "--json"];
  }
  if (command === "doctor") {
    return ["doctor", "--json"];
  }
  return ["up", "--lite"];
}

export function defaultLayoutPaths(settings: DefaultLayoutSettings): MemoStackPathPlan {
  const root = settings.rootFolder;
  const scope = `${root}/spaces/${settings.spaceSlug}/profiles/${settings.profileExternalRef}`;
  return {
    root,
    readme: normalizePath(`${root}/README.md`),
    generatedFacts: normalizePath(`${scope}/generated/facts`),
    inbox: normalizePath(`${scope}/inbox`),
    conflicts: normalizePath(`${scope}/conflicts`),
  };
}

export function safeRootFolder(value: string): string {
  const raw = value.trim();
  if (!raw) {
    throw new Error("Folder cannot be empty");
  }
  if (raw.startsWith("/") || raw.startsWith("\\") || /^[A-Za-z]:[\\/]/.test(raw)) {
    throw new Error("Folder must be relative to the vault");
  }
  const path = normalizePath(raw);
  if (path.startsWith("/")) {
    throw new Error("Folder must be relative to the vault");
  }
  for (const part of path.split("/")) {
    if (!part || part === "." || part === "..") {
      throw new Error("Folder cannot contain empty, dot, or parent segments");
    }
    if (hasControlOrZeroWidth(part)) {
      throw new Error("Folder contains unsafe formatting characters");
    }
  }
  return path;
}

export function safeScopeSegment(value: string, fallback: string): string {
  const raw = (value.trim() || fallback).trim();
  if (!raw) {
    throw new Error("Project and profile cannot be empty");
  }
  if (hasControlOrZeroWidth(raw)) {
    throw new Error("Project or profile contains unsafe formatting characters");
  }
  const normalized = raw.toLocaleLowerCase();
  let slug = normalized.replace(/[^a-z0-9_.-]+/g, "-").replace(/^-+|-+$/g, "");
  slug = slug.replace(/-{2,}/g, "-").replace(/^[._-]+|[._-]+$/g, "");
  if (!slug) {
    slug = "scope";
  }
  const changed = slug !== normalized || slug.length > 72;
  slug = slug.slice(0, 72).replace(/^[._-]+|[._-]+$/g, "") || "scope";
  if (changed) {
    slug = `${slug}--${sha256(raw).slice(0, 8)}`;
  }
  return slug;
}

export function summarizeResult(
  command: ConnectorCommand,
  result: ConnectorRunResult,
): string {
  const payload = asRecord(result.payload);
  if (!payload) {
    return result.exitCode === 0
      ? `Memo Stack ${command} finished.`
      : `Memo Stack ${command} failed. See developer console.`;
  }

  if (command === "connect") {
    return `Memo Stack connected: ${countArray(payload.written)} written, ${countArray(payload.skipped)} skipped.`;
  }

  if (command === "doctor") {
    const checks = Array.isArray(payload.checks) ? payload.checks : [];
    const failed = checks.filter((check) => {
      const item = asRecord(check);
      return item?.ok === false && item?.required !== false;
    }).length;
    return failed === 0
      ? `Memo Stack doctor: ${checks.length} checks passed.`
      : `Memo Stack doctor: ${failed} required check failed.`;
  }

  if (command === "preview") {
    const exportPayload = asRecord(payload.export);
    const importPayload = asRecord(payload.import);
    return [
      `Memo Stack preview: ${num(exportPayload, "would_export")} export`,
      `${num(importPayload, "would_update")} update`,
      `${num(importPayload, "would_suggest")} suggestion`,
      `${totalConflicts(exportPayload, importPayload)} conflict`,
    ].join(", ");
  }

  const importPayload = asRecord(payload.import);
  const exportPayload = asRecord(payload.export);
  if (payload.export_skipped === true) {
    return `Memo Stack sync paused: ${str(payload.export_skipped_reason)}`;
  }
  return [
    `Memo Stack sync: ${num(importPayload, "updated")} updated`,
    `${num(importPayload, "suggested")} suggested`,
    `${num(exportPayload, "exported")} exported`,
    `${totalConflicts(importPayload, exportPayload)} conflict`,
  ].join(", ");
}

export function summarizeLocalStackResult(
  command: LocalStackCommand,
  result: ConnectorRunResult,
): string {
  const payload = asRecord(result.payload);
  if (command === "init" && payload) {
    return result.exitCode === 0
      ? `Memo Stack local config initialized at ${str(payload.home)}.`
      : "Memo Stack local config was not initialized.";
  }
  if (command === "status" && payload) {
    const health = asRecord(payload.health);
    const healthOk = health?.status_code === 200;
    return healthOk
      ? `Memo Stack local status: API ready at ${str(payload.api_url)}.`
      : `Memo Stack local status: API not ready at ${str(payload.api_url)}.`;
  }
  if (command === "doctor" && payload) {
    const checks = Array.isArray(payload.checks) ? payload.checks : [];
    const failed = checks.filter((check) => asRecord(check)?.ok === false).length;
    return failed === 0
      ? `Memo Stack local doctor: ${checks.length} checks passed.`
      : `Memo Stack local doctor: ${failed} check failed.`;
  }
  if (command === "start-lite") {
    return result.exitCode === 0
      ? "Memo Stack local stack started."
      : "Memo Stack local stack did not start.";
  }
  return result.exitCode === 0
    ? `Memo Stack local ${command} finished.`
    : `Memo Stack local ${command} failed.`;
}

export function localStackApiReady(result: ConnectorRunResult): boolean {
  const payload = asRecord(result.payload);
  const health = asRecord(payload?.health);
  const capabilities = asRecord(payload?.capabilities);
  return health?.status_code === 200 && capabilities?.status_code === 200;
}

export function joinUrl(base: string, path: string): string {
  return `${base.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

export function parseJson(stdout: string): unknown {
  try {
    return JSON.parse(stdout);
  } catch (_error) {
    return undefined;
  }
}

export function exitCode(error: ExecFileException | null): number {
  if (!error) {
    return 0;
  }
  return typeof error.code === "number" ? error.code : 1;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object"
    ? (value as Record<string, unknown>)
    : null;
}

function sha256(value: string): string {
  const crypto = require("crypto") as typeof import("crypto");
  return crypto
    .createHash("sha256")
    .update(value.replace(/\r\n/g, "\n").replace(/\r/g, "\n"))
    .digest("hex");
}

function hasControlOrZeroWidth(value: string): boolean {
  return /[\x00-\x1f\x7f\u200b-\u200f\ufeff]/.test(value);
}

function num(record: Record<string, unknown> | null, key: string): number {
  const value = record?.[key];
  return typeof value === "number" ? value : 0;
}

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function countArray(value: unknown): number {
  return Array.isArray(value) ? value.length : 0;
}

function totalConflicts(
  first: Record<string, unknown> | null,
  second: Record<string, unknown> | null,
): number {
  return num(first, "conflicts") + num(second, "conflicts");
}
