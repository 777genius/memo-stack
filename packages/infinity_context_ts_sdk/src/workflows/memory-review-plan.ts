import type { RequestControls } from "../client.js";
import { ValueError } from "../payload.js";
import type {
  ContextLinkVisibleFilterInput,
  ReviewContextLinkSuggestionBatchItemInput,
  ReviewContextLinkSuggestionInput,
} from "../resources/context-links.js";
import type {
  ReviewSuggestionBatchItemInput,
  SuggestionReviewAction,
} from "../resources/suggestions.js";
import {
  mergeWorkflowControls,
  optional,
  requiredWorkflowText,
} from "./workflow-helpers.js";

export interface MemoryReviewDecisionDefaults extends RequestControls {
  readonly reason?: string;
  readonly continueOnError?: boolean;
}

export interface MemoryContextLinkReviewDecision {
  readonly suggestionId: string;
  readonly action?: ReviewContextLinkSuggestionInput["action"];
  readonly reason?: string;
  readonly targetType?: string;
  readonly targetId?: string;
  readonly relationType?: string;
  readonly confidence?: string;
  readonly linkReason?: string;
}

export interface MemorySuggestionReviewDecision {
  readonly suggestionId: string;
  readonly action?: SuggestionReviewAction;
  readonly reason?: string;
  readonly force?: boolean;
}

export interface MemoryContextLinkReviewPlanOptions extends MemoryReviewDecisionDefaults {
  readonly action?: ReviewContextLinkSuggestionInput["action"];
  readonly visibleFilter?: ContextLinkVisibleFilterInput;
  readonly items: readonly MemoryContextLinkReviewDecision[];
}

export interface MemorySuggestionReviewPlanOptions extends MemoryReviewDecisionDefaults {
  readonly action?: SuggestionReviewAction;
  readonly force?: boolean;
  readonly items: readonly MemorySuggestionReviewDecision[];
}

export interface CreateMemoryReviewPlanInput extends MemoryReviewDecisionDefaults {
  readonly contextLinks?: MemoryContextLinkReviewPlanOptions;
  readonly suggestions?: MemorySuggestionReviewPlanOptions;
}

export interface MemoryContextLinkReviewPlan {
  readonly items: readonly ReviewContextLinkSuggestionBatchItemInput[];
  readonly options: {
    readonly continueOnError?: boolean;
    readonly visibleFilter?: ContextLinkVisibleFilterInput;
  } & RequestControls;
}

export interface MemorySuggestionReviewPlan {
  readonly items: readonly ReviewSuggestionBatchItemInput[];
  readonly options: {
    readonly continueOnError?: boolean;
  } & RequestControls;
}

export interface MemoryReviewPlanSummary {
  readonly total: number;
  readonly contextLinkReviews: number;
  readonly suggestionReviews: number;
  readonly byAction: Readonly<Record<string, number>>;
}

export interface MemoryReviewPlan {
  readonly contextLinks?: MemoryContextLinkReviewPlan;
  readonly suggestions?: MemorySuggestionReviewPlan;
  readonly summary: MemoryReviewPlanSummary;
}

export function createMemoryReviewPlan(input: CreateMemoryReviewPlanInput): MemoryReviewPlan {
  const contextLinks = input.contextLinks === undefined
    ? undefined
    : contextLinkReviewPlan(input, input.contextLinks);
  const suggestions = input.suggestions === undefined
    ? undefined
    : suggestionReviewPlan(input, input.suggestions);
  const total = (contextLinks?.items.length ?? 0) + (suggestions?.items.length ?? 0);
  if (total === 0) {
    throw new ValueError("createMemoryReviewPlan requires at least one review item");
  }

  return Object.freeze({
    ...optional("contextLinks", contextLinks),
    ...optional("suggestions", suggestions),
    summary: Object.freeze({
      total,
      contextLinkReviews: contextLinks?.items.length ?? 0,
      suggestionReviews: suggestions?.items.length ?? 0,
      byAction: Object.freeze(actionCounts([
        ...(contextLinks?.items ?? []).map((item) => item.action),
        ...(suggestions?.items ?? []).map((item) => item.action),
      ])),
    }),
  });
}

function contextLinkReviewPlan(
  input: CreateMemoryReviewPlanInput,
  options: MemoryContextLinkReviewPlanOptions,
): MemoryContextLinkReviewPlan {
  const items = freezeArray(options.items.map((item, index) =>
    contextLinkReviewItem(input, options, item, index)
  ));

  return Object.freeze({
    items,
    options: Object.freeze({
      ...mergeWorkflowControls(input, options),
      ...optional("continueOnError", options.continueOnError ?? input.continueOnError),
      ...optional("visibleFilter", options.visibleFilter),
    }),
  });
}

function suggestionReviewPlan(
  input: CreateMemoryReviewPlanInput,
  options: MemorySuggestionReviewPlanOptions,
): MemorySuggestionReviewPlan {
  const items = freezeArray(options.items.map((item, index) =>
    suggestionReviewItem(input, options, item, index)
  ));

  return Object.freeze({
    items,
    options: Object.freeze({
      ...mergeWorkflowControls(input, options),
      ...optional("continueOnError", options.continueOnError ?? input.continueOnError),
    }),
  });
}

function contextLinkReviewItem(
  input: CreateMemoryReviewPlanInput,
  options: MemoryContextLinkReviewPlanOptions,
  item: MemoryContextLinkReviewDecision,
  index: number,
): ReviewContextLinkSuggestionBatchItemInput {
  return Object.freeze({
    suggestionId: requiredWorkflowText(item.suggestionId, `context link review item ${index} requires suggestionId`),
    action: item.action ?? options.action ?? "approve",
    ...optional("reason", item.reason ?? options.reason ?? input.reason),
    ...optional("targetType", item.targetType),
    ...optional("targetId", item.targetId),
    ...optional("relationType", item.relationType),
    ...optional("confidence", item.confidence),
    ...optional("linkReason", item.linkReason),
  });
}

function suggestionReviewItem(
  input: CreateMemoryReviewPlanInput,
  options: MemorySuggestionReviewPlanOptions,
  item: MemorySuggestionReviewDecision,
  index: number,
): ReviewSuggestionBatchItemInput {
  return Object.freeze({
    suggestionId: requiredWorkflowText(item.suggestionId, `suggestion review item ${index} requires suggestionId`),
    action: item.action ?? options.action ?? "approve",
    ...optional("reason", item.reason ?? options.reason ?? input.reason),
    ...optional("force", item.force ?? options.force),
  });
}

function actionCounts(actions: readonly string[]): Readonly<Record<string, number>> {
  const counts: Record<string, number> = {};
  for (const action of actions) {
    counts[action] = (counts[action] ?? 0) + 1;
  }
  return counts;
}

function freezeArray<TValue>(values: readonly TValue[]): readonly TValue[] {
  return Object.freeze([...values]);
}
