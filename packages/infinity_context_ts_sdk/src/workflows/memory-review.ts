import { ValueError } from "../payload.js";
import type {
  ContextLinksClient,
  ReviewContextLinkSuggestionsBatchData,
} from "../resources/context-links.js";
import type {
  ReviewSuggestionsBatchData,
  SuggestionsClient,
} from "../resources/suggestions.js";
import type { ApiEnvelope } from "../types.js";
import type {
  MemoryReviewPlan,
  MemoryReviewPlanSummary,
} from "./memory-review-plan.js";
import { uniqueStrings } from "./workflow-helpers.js";

export interface MemoryReviewResources {
  readonly contextLinks: ContextLinksClient;
  readonly suggestions?: SuggestionsClient;
}

export interface ApplyMemoryReviewPlanSummary extends MemoryReviewPlanSummary {
  readonly applied: number;
  readonly failed: number;
  readonly stopped: boolean;
}

export interface ApplyMemoryReviewPlanDiagnostics {
  readonly ok: boolean;
  readonly contextLinksOk: boolean | null;
  readonly suggestionsOk: boolean | null;
  readonly warnings: readonly string[];
}

export interface ApplyMemoryReviewPlanResult {
  readonly contextLinks?: ApiEnvelope<ReviewContextLinkSuggestionsBatchData>;
  readonly suggestions?: ApiEnvelope<ReviewSuggestionsBatchData>;
  readonly summary: ApplyMemoryReviewPlanSummary;
  readonly diagnostics: ApplyMemoryReviewPlanDiagnostics;
}

export async function applyMemoryReviewPlan(
  resources: MemoryReviewResources,
  plan: MemoryReviewPlan,
): Promise<ApplyMemoryReviewPlanResult> {
  const hasContextLinkReviews = (plan.contextLinks?.items.length ?? 0) > 0;
  const hasSuggestionReviews = (plan.suggestions?.items.length ?? 0) > 0;
  if (!hasContextLinkReviews && !hasSuggestionReviews) {
    throw new ValueError("applyMemoryReviewPlan requires at least one review item");
  }

  const [contextLinks, suggestions] = await Promise.all([
    hasContextLinkReviews && plan.contextLinks !== undefined
      ? resources.contextLinks.reviewContextLinkSuggestionsBatch(
          plan.contextLinks.items,
          plan.contextLinks.options,
        )
      : Promise.resolve(undefined),
    hasSuggestionReviews && plan.suggestions !== undefined
      ? suggestionsResource(resources).reviewSuggestionsBatch(plan.suggestions.items, plan.suggestions.options)
      : Promise.resolve(undefined),
  ]);

  const contextLinksOk = batchOk(contextLinks?.data);
  const suggestionsOk = batchOk(suggestions?.data);
  const warnings = uniqueStrings([
    ...(contextLinksOk === false
      ? [`context link review failed ${contextLinks?.data.failed ?? 0} item(s)`]
      : []),
    ...(suggestionsOk === false
      ? [`suggestion review failed ${suggestions?.data.failed ?? 0} item(s)`]
      : []),
  ]);

  return {
    ...(contextLinks ? { contextLinks } : {}),
    ...(suggestions ? { suggestions } : {}),
    summary: {
      ...plan.summary,
      applied: (contextLinks?.data.applied ?? 0) + (suggestions?.data.applied ?? 0),
      failed: (contextLinks?.data.failed ?? 0) + (suggestions?.data.failed ?? 0),
      stopped: (contextLinks?.data.stopped ?? false) || (suggestions?.data.stopped ?? false),
    },
    diagnostics: {
      ok: (contextLinksOk ?? true) && (suggestionsOk ?? true),
      contextLinksOk,
      suggestionsOk,
      warnings,
    },
  };
}

function suggestionsResource(resources: MemoryReviewResources): SuggestionsClient {
  if (resources.suggestions === undefined) {
    throw new ValueError("applyMemoryReviewPlan requires MemoryWorkflowResources: suggestions");
  }
  return resources.suggestions;
}

function batchOk(
  data: { readonly failed: number; readonly stopped: boolean } | undefined,
): boolean | null {
  if (data === undefined) {
    return null;
  }
  return data.failed === 0 && !data.stopped;
}
