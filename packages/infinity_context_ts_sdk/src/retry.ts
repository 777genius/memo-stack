import type { HttpMethod } from "./transport.js";

export interface RetryPolicy {
  readonly maxAttempts: number;
  readonly baseDelayMs: number;
  readonly maxDelayMs: number;
  readonly jitter: boolean;
}

export const DEFAULT_RETRY_POLICY: RetryPolicy = {
  maxAttempts: 2,
  baseDelayMs: 100,
  maxDelayMs: 1000,
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

export function retryDelayMs(policy: RetryPolicy, attemptIndex: number): number {
  const exponential = Math.min(policy.maxDelayMs, policy.baseDelayMs * 2 ** attemptIndex);
  if (!policy.jitter) {
    return exponential;
  }
  return Math.floor(exponential * (0.5 + Math.random() * 0.5));
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    const timeout = setTimeout(resolve, ms);
    timeout.unref?.();
  });
}
