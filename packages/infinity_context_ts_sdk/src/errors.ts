import type { JsonValue } from "./types.js";

const SENSITIVE_KEY_MARKERS = [
  "api_key",
  "apikey",
  "token",
  "secret",
  "password",
  "passwd",
  "credential",
  "authorization",
  "bearer",
] as const;

export interface InfinityContextErrorOptions {
  readonly statusCode: number;
  readonly code: string;
  readonly message: string;
  readonly retryable: boolean;
  readonly details?: JsonValue | undefined;
  readonly requestId?: string | undefined;
}

export class InfinityContextError extends Error {
  readonly statusCode: number;
  readonly code: string;
  readonly retryable: boolean;
  readonly details: JsonValue | undefined;
  readonly requestId: string | undefined;

  constructor(options: InfinityContextErrorOptions) {
    super(redactSensitiveText(options.message).slice(0, 500));
    this.name = "InfinityContextError";
    this.statusCode = options.statusCode;
    this.code = options.code;
    this.retryable = options.retryable;
    this.details = redactJson(options.details);
    this.requestId = options.requestId;
  }
}

export function networkError(cause: unknown): InfinityContextError {
  const message = cause instanceof Error ? cause.message : "Infinity Context request failed";
  return new InfinityContextError({
    statusCode: 0,
    code: "memory.network_error",
    message,
    retryable: true,
  });
}

export function redactSensitiveText(value: string): string {
  return value
    .replace(/(authorization:\s*)(?:bearer\s+)?[A-Za-z0-9._~+/=-]+/gi, "$1[REDACTED]")
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, "Bearer [REDACTED]")
    .replace(/([?&](?:token|api_key|apikey|secret|password)=)[^&\s]+/gi, "$1[REDACTED]")
    .replace(/(authorization:\s*)[^\n\r\s]+/gi, "$1[REDACTED]");
}

export function redactJson(value: JsonValue | undefined): JsonValue | undefined {
  if (value === undefined || value === null || typeof value !== "object") {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => redactJson(item) ?? null);
  }
  const output: Record<string, JsonValue | undefined> = {};
  for (const [key, item] of Object.entries(value)) {
    const normalized = key.toLowerCase();
    output[key] = SENSITIVE_KEY_MARKERS.some((marker) => normalized.includes(marker))
      ? "[REDACTED]"
      : redactJson(item);
  }
  return output;
}
