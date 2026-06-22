import type { HttpMethod } from "./transport.js";

export interface RetryPolicy {
  readonly maxAttempts: number;
  readonly baseDelayMs: number;
  readonly maxDelayMs: number;
  readonly maxRetryAfterMs: number;
  readonly jitter: boolean;
}

export const DEFAULT_RETRY_POLICY: RetryPolicy = {
  maxAttempts: 2,
  baseDelayMs: 100,
  maxDelayMs: 1000,
  maxRetryAfterMs: 60_000,
  jitter: true,
};

export interface RetryDecisionInput {
  readonly method: HttpMethod;
  readonly status?: number;
  readonly retryableError?: boolean;
  readonly hasIdempotencyKey: boolean;
}

export function shouldRetry(input: RetryDecisionInput): boolean {
  const methodIsSafe = input.method === "GET";
  const methodIsRepeatable = methodIsSafe || input.hasIdempotencyKey;
  if (!methodIsRepeatable) {
    return false;
  }
  if (input.retryableError) {
    return true;
  }
  return input.status === 429 || input.status === 408 || (input.status !== undefined && input.status >= 500);
}

export function retryDelayMs(policy: RetryPolicy, attemptIndex: number, retryAfterMs?: number | undefined): number {
  const serverDelayMs = boundedRetryAfterMs(retryAfterMs, policy.maxRetryAfterMs);
  if (serverDelayMs !== undefined) {
    return serverDelayMs;
  }

  const exponential = Math.min(policy.maxDelayMs, policy.baseDelayMs * 2 ** attemptIndex);
  if (!policy.jitter) {
    return exponential;
  }
  return Math.floor(exponential * (0.5 + Math.random() * 0.5));
}

export function parseRetryAfterMs(value: string | null | undefined, nowMs = Date.now()): number | undefined {
  const trimmed = value?.trim();
  if (!trimmed) {
    return undefined;
  }

  const seconds = Number(trimmed);
  if (Number.isFinite(seconds) && seconds >= 0) {
    return Math.ceil(seconds * 1000);
  }

  const dateMs = Date.parse(trimmed);
  if (!Number.isFinite(dateMs)) {
    return undefined;
  }

  return Math.max(0, dateMs - nowMs);
}

function boundedRetryAfterMs(
  retryAfterMs: number | undefined,
  maxRetryAfterMs: number,
): number | undefined {
  if (retryAfterMs === undefined || !Number.isFinite(retryAfterMs) || retryAfterMs < 0) {
    return undefined;
  }
  if (!Number.isFinite(maxRetryAfterMs) || maxRetryAfterMs < 0) {
    return retryAfterMs;
  }

  return Math.min(retryAfterMs, maxRetryAfterMs);
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    const timeout = setTimeout(resolve, ms);
    timeout.unref?.();
  });
}
