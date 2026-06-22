import type { RequestControls } from "../client.js";
import { ValueError } from "../payload.js";
import type { ExportsClient } from "../resources/exports.js";
import type { JsonObject } from "../types.js";
import {
  jsonObjectField,
  optional,
  requiredWorkflowText,
  workflowControls,
} from "./workflow-helpers.js";

export type MemorySnapshotTransferMode = "export_only" | "preview" | "dry_run" | "confirmed_import";

export interface TransferMemorySnapshotInput extends RequestControls {
  readonly sourceSpaceSlug: string;
  readonly sourceMemoryScopeExternalRef: string;
  readonly targetSpaceSlug?: string;
  readonly targetMemoryScopeExternalRef?: string;
  readonly mode?: MemorySnapshotTransferMode;
  readonly redacted?: boolean;
  readonly mergeStrategy?: string;
  readonly confirmed?: boolean;
  readonly sourceName?: string;
}

export interface MemorySnapshotTransferEndpoint {
  readonly spaceSlug: string;
  readonly memoryScopeExternalRef: string;
}

export interface MemorySnapshotTransferDiagnostics {
  readonly mode: MemorySnapshotTransferMode;
  readonly mutated: boolean;
  readonly redacted: boolean;
  readonly mergeStrategy: string;
  readonly warnings: readonly string[];
}

export interface TransferMemorySnapshotResult {
  readonly source: MemorySnapshotTransferEndpoint;
  readonly target: MemorySnapshotTransferEndpoint;
  readonly snapshot: JsonObject;
  readonly manifest?: JsonObject;
  readonly preview?: JsonObject;
  readonly importResult?: JsonObject;
  readonly diagnostics: MemorySnapshotTransferDiagnostics;
}

export async function transferMemorySnapshot(
  exportsClient: ExportsClient,
  input: TransferMemorySnapshotInput,
): Promise<TransferMemorySnapshotResult> {
  const controls = workflowControls(input);
  const mode = input.mode ?? "preview";
  const redacted = input.redacted ?? true;
  const mergeStrategy = input.mergeStrategy ?? "fail_on_conflict";
  const source = snapshotSource(input);
  const target = snapshotTarget(input);
  const warnings = snapshotTransferWarnings(input, mode, source, target);
  validateSnapshotTransfer(input, mode);

  const snapshotExport = await exportsClient.exportMemoryScopeSnapshot({
    ...controls,
    spaceSlug: source.spaceSlug,
    memoryScopeExternalRef: source.memoryScopeExternalRef,
    redacted,
  });
  const snapshot = jsonObjectField(snapshotExport, "data");
  if (snapshot === undefined) {
    throw new ValueError("Snapshot export response did not include data");
  }
  const manifest = jsonObjectField(snapshotExport, "manifest");

  if (mode === "export_only") {
    return snapshotTransferResult(source, target, snapshot, manifest, {
      mode,
      redacted,
      mergeStrategy,
      warnings,
    });
  }

  if (mode === "preview") {
    const preview = await exportsClient.previewMemoryScopeSnapshotImport({
      ...controls,
      spaceSlug: target.spaceSlug,
      memoryScopeExternalRef: target.memoryScopeExternalRef,
      snapshot,
      ...optional("manifest", manifest),
      mergeStrategy,
    });

    return snapshotTransferResult(source, target, snapshot, manifest, {
      mode,
      redacted,
      mergeStrategy,
      warnings,
      preview,
    });
  }

  const importResult = await exportsClient.importMemoryScopeSnapshot({
    ...controls,
    spaceSlug: target.spaceSlug,
    memoryScopeExternalRef: target.memoryScopeExternalRef,
    snapshot,
    ...optional("manifest", manifest),
    dryRun: mode === "dry_run",
    mergeStrategy,
    confirmed: mode === "confirmed_import",
    sourceName: input.sourceName ?? "ts-sdk-transfer-memory-snapshot",
  });

  return snapshotTransferResult(source, target, snapshot, manifest, {
    mode,
    redacted,
    mergeStrategy,
    warnings,
    importResult,
  });
}

function snapshotSource(input: TransferMemorySnapshotInput): MemorySnapshotTransferEndpoint {
  return {
    spaceSlug: requiredWorkflowText(input.sourceSpaceSlug, "transferMemorySnapshot requires sourceSpaceSlug"),
    memoryScopeExternalRef: requiredWorkflowText(
      input.sourceMemoryScopeExternalRef,
      "transferMemorySnapshot requires sourceMemoryScopeExternalRef",
    ),
  };
}

function snapshotTarget(input: TransferMemorySnapshotInput): MemorySnapshotTransferEndpoint {
  const targetSpaceSlug = input.targetSpaceSlug ?? input.sourceSpaceSlug;
  const targetMemoryScopeExternalRef = input.targetMemoryScopeExternalRef ?? input.sourceMemoryScopeExternalRef;
  return {
    spaceSlug: requiredWorkflowText(targetSpaceSlug, "transferMemorySnapshot requires targetSpaceSlug"),
    memoryScopeExternalRef: requiredWorkflowText(
      targetMemoryScopeExternalRef,
      "transferMemorySnapshot requires targetMemoryScopeExternalRef",
    ),
  };
}

function validateSnapshotTransfer(input: TransferMemorySnapshotInput, mode: MemorySnapshotTransferMode): void {
  if (mode === "confirmed_import" && input.confirmed !== true) {
    throw new ValueError("confirmed_import requires confirmed: true");
  }
  if (mode === "dry_run" && input.confirmed === true) {
    throw new ValueError("dry_run must not set confirmed: true");
  }
}

function snapshotTransferWarnings(
  input: TransferMemorySnapshotInput,
  mode: MemorySnapshotTransferMode,
  source: MemorySnapshotTransferEndpoint,
  target: MemorySnapshotTransferEndpoint,
): readonly string[] {
  const warnings: string[] = [];
  if (mode === "confirmed_import") {
    warnings.push("confirmed_import mutates target memory scope");
  }
  if (input.redacted ?? true) {
    warnings.push("redacted snapshots may omit restricted source fields");
  }
  if (source.spaceSlug === target.spaceSlug && source.memoryScopeExternalRef === target.memoryScopeExternalRef) {
    warnings.push("source and target memory scope are the same");
  }
  return warnings;
}

function snapshotTransferResult(
  source: MemorySnapshotTransferEndpoint,
  target: MemorySnapshotTransferEndpoint,
  snapshot: JsonObject,
  manifest: JsonObject | undefined,
  input: {
    readonly mode: MemorySnapshotTransferMode;
    readonly redacted: boolean;
    readonly mergeStrategy: string;
    readonly warnings: readonly string[];
    readonly preview?: JsonObject;
    readonly importResult?: JsonObject;
  },
): TransferMemorySnapshotResult {
  return {
    source,
    target,
    snapshot,
    ...optional("manifest", manifest),
    ...optional("preview", input.preview),
    ...optional("importResult", input.importResult),
    diagnostics: {
      mode: input.mode,
      mutated: input.mode === "confirmed_import",
      redacted: input.redacted,
      mergeStrategy: input.mergeStrategy,
      warnings: input.warnings,
    },
  };
}
