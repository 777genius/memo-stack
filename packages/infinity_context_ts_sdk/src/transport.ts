import { networkError } from "./errors.js";
import type { JsonValue, QueryParams } from "./types.js";

export type HttpMethod = "GET" | "POST" | "PATCH" | "DELETE" | "PUT";

export type HttpBody =
  | { readonly kind: "json"; readonly value: JsonValue }
  | { readonly kind: "bytes"; readonly value: BodyInit; readonly contentType?: string | undefined };

export interface HttpRequest {
  readonly method: HttpMethod;
  readonly url: URL;
  readonly headers: Headers;
  readonly body?: HttpBody | undefined;
  readonly signal?: AbortSignal | undefined;
  readonly responseType?: "json" | "bytes" | undefined;
}

export interface HttpResponse {
  readonly status: number;
  readonly headers: Headers;
  readonly body: string | Uint8Array;
}

export interface HttpTransport {
  send(request: HttpRequest): Promise<HttpResponse>;
}

export type FetchLike = typeof fetch;

export interface TimeoutSignal {
  readonly signal?: AbortSignal | undefined;
  readonly cleanup: () => void;
}

export class FetchTransport implements HttpTransport {
  readonly #fetch: FetchLike;

  constructor(fetchLike: FetchLike = fetch) {
    this.#fetch = fetchLike;
  }

  async send(request: HttpRequest): Promise<HttpResponse> {
    const headers = new Headers(request.headers);
    let body: BodyInit | undefined;

    if (request.body?.kind === "json") {
      headers.set("Content-Type", headers.get("Content-Type") ?? "application/json");
      body = JSON.stringify(request.body.value);
    } else if (request.body?.kind === "bytes") {
      body = request.body.value;
      if (request.body.contentType) {
        headers.set("Content-Type", request.body.contentType);
      }
    }

    try {
      const init: RequestInit = {
        method: request.method,
        headers,
      };
      if (body !== undefined) {
        init.body = body;
      }
      if (request.signal !== undefined) {
        init.signal = request.signal;
      }
      const response = await this.#fetch(request.url, init);
      return {
        status: response.status,
        headers: response.headers,
        body:
          request.responseType === "bytes"
            ? new Uint8Array(await response.arrayBuffer())
            : await response.text(),
      };
    } catch (error) {
      throw networkError(error);
    }
  }
}

export function buildUrl(baseUrl: string, path: string, params?: QueryParams): URL {
  const url = new URL(path, baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`);
  for (const [key, rawValue] of Object.entries(params ?? {})) {
    if (rawValue === undefined || rawValue === null) {
      continue;
    }
    if (Array.isArray(rawValue)) {
      for (const item of rawValue as readonly unknown[]) {
        url.searchParams.append(key, String(item));
      }
      continue;
    }
    url.searchParams.set(key, String(rawValue));
  }
  return url;
}

export function withTimeout(signal: AbortSignal | undefined, timeoutMs: number): TimeoutSignal {
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    return {
      ...(signal !== undefined ? { signal } : {}),
      cleanup: () => undefined,
    };
  }

  const timeoutController = new AbortController();
  const timeout = setTimeout(() => {
    timeoutController.abort(new DOMException("Request timed out", "TimeoutError"));
  }, timeoutMs);
  timeout.unref?.();

  if (!signal) {
    return {
      signal: timeoutController.signal,
      cleanup: () => clearTimeout(timeout),
    };
  }

  const controller = new AbortController();
  let cleanedUp = false;
  const cleanup = () => {
    if (cleanedUp) {
      return;
    }
    cleanedUp = true;
    clearTimeout(timeout);
    signal.removeEventListener("abort", onAbort);
    timeoutController.signal.removeEventListener("abort", onTimeout);
  };
  const abort = (reason?: unknown) => {
    cleanup();
    if (!controller.signal.aborted) {
      controller.abort(reason);
    }
  };
  const onAbort = () => abort(signal.reason);
  const onTimeout = () => abort(timeoutController.signal.reason);

  if (signal.aborted) {
    abort(signal.reason);
    return {
      signal: controller.signal,
      cleanup,
    };
  }

  signal.addEventListener("abort", onAbort, { once: true });
  timeoutController.signal.addEventListener("abort", onTimeout, { once: true });
  return {
    signal: controller.signal,
    cleanup,
  };
}
