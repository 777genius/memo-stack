import { resolveAuthToken, type AuthTokenProvider } from "./auth.js";
import { InfinityContextError, networkError, redactSensitiveText } from "./errors.js";
import { DEFAULT_RETRY_POLICY, retryDelayMs, shouldRetry, sleep, type RetryPolicy } from "./retry.js";
import { buildUrl, FetchTransport, type HttpBody, type HttpMethod, type HttpTransport, withTimeout } from "./transport.js";
import type { JsonValue, QueryParams } from "./types.js";

export interface InfinityContextClientOptions {
  readonly baseUrl?: string;
  readonly token?: AuthTokenProvider;
  readonly timeoutMs?: number;
  readonly transport?: HttpTransport;
  readonly retryPolicy?: Partial<RetryPolicy>;
  readonly sleep?: (ms: number) => Promise<void>;
}

export interface RequestOptions {
  readonly method: HttpMethod;
  readonly path: string;
  readonly params?: QueryParams | undefined;
  readonly json?: JsonValue | undefined;
  readonly bytes?: BodyInit | undefined;
  readonly contentType?: string | undefined;
  readonly headers?: Record<string, string> | undefined;
  readonly idempotencyKey?: string | undefined;
  readonly signal?: AbortSignal | undefined;
  readonly responseType?: "json" | "bytes" | undefined;
}

export interface RequestExecutor {
  request<T = JsonValue>(options: RequestOptions): Promise<T>;
}

export class HttpClient implements RequestExecutor {
  readonly #baseUrl: string;
  readonly #token: AuthTokenProvider;
  readonly #timeoutMs: number;
  readonly #transport: HttpTransport;
  readonly #retryPolicy: RetryPolicy;
  readonly #sleep: (ms: number) => Promise<void>;

  constructor(options: InfinityContextClientOptions = {}) {
    this.#baseUrl = options.baseUrl ?? "http://127.0.0.1:7788";
    this.#token = options.token;
    this.#timeoutMs = options.timeoutMs ?? 10_000;
    this.#transport = options.transport ?? new FetchTransport();
    this.#retryPolicy = { ...DEFAULT_RETRY_POLICY, ...options.retryPolicy };
    this.#sleep = options.sleep ?? sleep;
  }

  async request<T = JsonValue>(options: RequestOptions): Promise<T> {
    let lastError: InfinityContextError | undefined;
    const maxAttempts = Math.max(1, this.#retryPolicy.maxAttempts);

    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      try {
        const response = await this.#send(options);
        if (response.status < 400) {
          if (options.responseType === "bytes") {
            return response.body as T;
          }
          return parseJson(response.body as string) as T;
        }

        const error = toHttpError(response.status, response.headers, response.body as string);
        lastError = error;
        if (
          attempt + 1 >= maxAttempts ||
          !shouldRetry({
            method: options.method,
            status: response.status,
            hasIdempotencyKey: Boolean(options.idempotencyKey),
          })
        ) {
          throw error;
        }
      } catch (error) {
        const sdkError = error instanceof InfinityContextError ? error : networkError(error);
        lastError = sdkError;
        if (
          attempt + 1 >= maxAttempts ||
          !shouldRetry({
            method: options.method,
            retryableError: sdkError.retryable,
            hasIdempotencyKey: Boolean(options.idempotencyKey),
          })
        ) {
          throw sdkError;
        }
      }

      await this.#sleep(retryDelayMs(this.#retryPolicy, attempt));
    }

    throw lastError ?? new InfinityContextError({
      statusCode: 0,
      code: "memory.request_failed",
      message: "Infinity Context request failed",
      retryable: true,
    });
  }

  async #send(options: RequestOptions) {
    const headers = new Headers(options.headers);
    const token = await resolveAuthToken(this.#token);
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    if (options.idempotencyKey) {
      headers.set("Idempotency-Key", options.idempotencyKey);
    }

    let body: HttpBody | undefined;
    if (options.json !== undefined) {
      body = { kind: "json", value: options.json };
    } else if (options.bytes !== undefined) {
      body = { kind: "bytes", value: options.bytes, contentType: options.contentType };
    }

    return this.#transport.send({
      method: options.method,
      url: buildUrl(this.#baseUrl, options.path, options.params),
      headers,
      body,
      signal: withTimeout(options.signal, this.#timeoutMs),
      responseType: options.responseType,
    });
  }
}

function parseJson(body: string): JsonValue {
  if (!body.trim()) {
    return {};
  }
  return JSON.parse(body) as JsonValue;
}

function toHttpError(statusCode: number, headers: Headers, body: string): InfinityContextError {
  const payload = safeJsonObject(body);
  const errorPayload = asRecord(payload.error);
  const detailPayload = asRecord(payload.detail);
  const code = String(errorPayload.code ?? detailPayload.code ?? "memory.http_error");
  const message = String((errorPayload.message ?? detailPayload.message ?? body) || code);
  const requestId = headers.get("x-request-id") ?? undefined;
  return new InfinityContextError({
    statusCode,
    code,
    message: redactSensitiveText(message),
    retryable: Boolean(errorPayload.retryable ?? statusCode >= 500),
    details: payload,
    requestId,
  });
}

function safeJsonObject(body: string): Record<string, JsonValue | undefined> {
  try {
    const parsed = JSON.parse(body) as JsonValue;
    return asRecord(parsed);
  } catch {
    return {};
  }
}

function asRecord(value: unknown): Record<string, JsonValue | undefined> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, JsonValue | undefined>)
    : {};
}
