import type { ContextDiagnostics } from "./context-types.js";

export type ContextRetrievalComponent = "vector" | "graph" | "rag";

export interface ContextRetrievalDiagnostics {
  readonly component: ContextRetrievalComponent;
  readonly status?: string | undefined;
  readonly queryCount?: number | undefined;
  readonly queryLimit?: number | undefined;
  readonly candidateCount?: number | undefined;
  readonly hydratedCount?: number | undefined;
  readonly staleDropCount?: number | undefined;
  readonly degradedCount?: number | undefined;
  readonly degradedReason?: string | undefined;
  readonly degradedStep?: string | undefined;
  readonly deadlineSeconds?: number | undefined;
}

export function retrievalDiagnostics(
  diagnostics: ContextDiagnostics,
  component: ContextRetrievalComponent,
): ContextRetrievalDiagnostics {
  return {
    component,
    status: stringField(diagnostics, `${component}_status`),
    queryCount: numberField(diagnostics, `${component}_query_count`),
    queryLimit: numberField(diagnostics, `${component}_query_limit`),
    candidateCount: numberField(diagnostics, `${component}_candidate_count`),
    hydratedCount: numberField(diagnostics, `${component}_hydrated_count`),
    staleDropCount: numberField(diagnostics, `stale_${component}_drop_count`),
    degradedCount: numberField(diagnostics, `${component}_query_degraded_count`),
    degradedReason: stringField(diagnostics, `${component}_degraded_reason`),
    degradedStep: stringField(diagnostics, `${component}_degraded_step`),
    deadlineSeconds: numberField(diagnostics, `${component}_deadline_seconds`),
  };
}

export function usedDerivedRetrieval(diagnostics: ContextDiagnostics): boolean {
  return (["vector", "graph", "rag"] as const).some(
    (component) => (retrievalDiagnostics(diagnostics, component).queryCount ?? 0) > 0,
  );
}

export function healthyRetrievalComponents(
  diagnostics: ContextDiagnostics,
  components: readonly ContextRetrievalComponent[] = ["vector", "graph"],
): boolean {
  return components.every((component) => {
    const status = retrievalDiagnostics(diagnostics, component).status;
    return status === "ok";
  });
}

function stringField(diagnostics: ContextDiagnostics, field: string): string | undefined {
  const value = diagnostics[field];

  return typeof value === "string" ? value : undefined;
}

function numberField(diagnostics: ContextDiagnostics, field: string): number | undefined {
  const value = diagnostics[field];

  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}
