import { describe, expect, it } from "vitest";
import {
  InfinityContextClient,
  InfinityContextError,
  MemoryScope,
  ReadScope,
  ValueError,
  healthyRetrievalComponents,
  retrievalDiagnostics,
  usedDerivedRetrieval,
  type HttpRequest,
  type HttpResponse,
  type HttpTransport,
} from "../src/index.js";

class RecordingTransport implements HttpTransport {
  readonly requests: HttpRequest[] = [];
  readonly bodies: unknown[] = [];
  #responses: HttpResponse[];

  constructor(responses: HttpResponse[]) {
    this.#responses = [...responses];
  }

  async send(request: HttpRequest): Promise<HttpResponse> {
    this.requests.push(request);
    if (request.body?.kind === "json") {
      this.bodies.push(request.body.value);
    }
    return this.#responses.shift() ?? jsonResponse({ data: { ok: true } });
  }
}

describe("InfinityContextClient", () => {
  it("sends auth, params and idempotency headers through resource clients", async () => {
    const transport = new RecordingTransport([jsonResponse({ data: { id: "fact_1" } })]);
    const client = new InfinityContextClient({
      baseUrl: "http://memory.test",
      token: async () => "test-token",
      transport,
      retryPolicy: { maxAttempts: 1 },
    });

    await client.facts.rememberFact({
      spaceId: "space_1",
      memoryScopeId: "scope_1",
      text: "Remember user likes source-rich summaries.",
      sourceRefs: [{ source_type: "test", source_id: "case_1" }],
      idempotencyKey: "case_1",
      category: "preference",
      tags: ["summary"],
    });

    expect(transport.requests[0]?.url.toString()).toBe("http://memory.test/v1/facts");
    expect(transport.requests[0]?.headers.get("authorization")).toBe("Bearer test-token");
    expect(transport.requests[0]?.headers.get("idempotency-key")).toBe("case_1");
    expect(transport.bodies[0]).toMatchObject({
      space_id: "space_1",
      memory_scope_id: "scope_1",
      text: "Remember user likes source-rich summaries.",
      category: "preference",
      tags: ["summary"],
    });
  });

  it("maps external read scopes to typed context payloads", async () => {
    const transport = new RecordingTransport([
      jsonResponse({
        data: {
          bundle_id: "bundle_1",
          rendered_text: "",
          items: [],
          top_evidence: [],
          answer_support: {
            status: "insufficient_evidence",
            items_returned: 0,
            coverage: {},
            policy: {},
            warnings: [],
          },
          diagnostics: {
            vector_status: "ok",
            graph_status: "ok",
            rag_status: "ok",
            query_decomposition_status: "available",
            query_decomposition_count: 2,
            query_decomposition_reasons: ["decomposition_event_context"],
            vector_query_count: 6,
            vector_query_limit: 15,
            vector_query_degraded_count: 0,
            graph_query_count: 4,
            graph_query_limit: 10,
            graph_query_degraded_count: 0,
            rag_query_count: 5,
            rag_query_limit: 12,
            rag_candidate_count: 7,
            rag_hydrated_count: 3,
            rag_query_degraded_count: 0,
          },
        },
      }),
    ]);
    const client = new InfinityContextClient({
      baseUrl: "http://memory.test",
      transport,
      retryPolicy: { maxAttempts: 1 },
    });

    const response = await client.context.buildContext({
      query: "daily digest preferences",
      readScope: ReadScope.external({
        spaceSlug: "social-monitor:tenant:workspace",
        memoryScopeExternalRefs: ["workspace-global", "user:user_1"],
      }),
      includeStale: false,
    });

    expect(response.data.diagnostics.query_decomposition_status).toBe("available");
    expect(response.data.diagnostics.vector_status).toBe("ok");
    expect(response.data.diagnostics.graph_status).toBe("ok");
    expect(response.data.diagnostics.vector_query_count).toBe(6);
    expect(response.data.diagnostics.graph_query_count).toBe(4);
    expect(response.data.diagnostics.rag_query_count).toBe(5);
    expect(usedDerivedRetrieval(response.data.diagnostics)).toBe(true);
    expect(healthyRetrievalComponents(response.data.diagnostics, ["vector", "graph", "rag"])).toBe(true);
    expect(retrievalDiagnostics(response.data.diagnostics, "rag")).toEqual({
      component: "rag",
      status: "ok",
      queryCount: 5,
      queryLimit: 12,
      candidateCount: 7,
      hydratedCount: 3,
      staleDropCount: undefined,
      degradedCount: 0,
      degradedReason: undefined,
      degradedStep: undefined,
      deadlineSeconds: undefined,
    });
    expect(transport.requests[0]?.url.toString()).toBe("http://memory.test/v1/context");
    expect(transport.bodies[0]).toMatchObject({
      space_slug: "social-monitor:tenant:workspace",
      memory_scope_external_refs: ["workspace-global", "user:user_1"],
      query: "daily digest preferences",
      token_budget: 1800,
      max_facts: 20,
      max_chunks: 30,
    });
    expect(transport.bodies[0]).not.toHaveProperty("include_stale");
  });

  it("keeps unsafe writes from retrying unless an idempotency key exists", async () => {
    const noRetryTransport = new RecordingTransport([
      jsonResponse({ error: { code: "temporary", message: "try again", retryable: true } }, 503),
      jsonResponse({ data: { id: "fact_1" } }),
    ]);
    const noRetryClient = new InfinityContextClient({
      baseUrl: "http://memory.test",
      transport: noRetryTransport,
      sleep: async () => undefined,
      retryPolicy: { maxAttempts: 2, jitter: false },
    });

    await expect(
      noRetryClient.facts.updateFact("fact_1", {
        expectedVersion: 1,
        text: "updated",
        reason: "test",
        sourceRefs: [{ source_type: "test", source_id: "case" }],
      }),
    ).rejects.toBeInstanceOf(InfinityContextError);
    expect(noRetryTransport.requests).toHaveLength(1);

    const retryTransport = new RecordingTransport([
      jsonResponse({ error: { code: "temporary", message: "try again", retryable: true } }, 503),
      jsonResponse({ data: { id: "doc_1" } }),
    ]);
    const retryClient = new InfinityContextClient({
      baseUrl: "http://memory.test",
      transport: retryTransport,
      sleep: async () => undefined,
      retryPolicy: { maxAttempts: 2, jitter: false },
    });

    await retryClient.documents.processDocument("doc_1", { idempotencyKey: "process:doc_1" });

    expect(retryTransport.requests).toHaveLength(2);
    expect(retryTransport.requests[1]?.headers.get("idempotency-key")).toBe("process:doc_1");
  });

  it("redacts sensitive data from HTTP errors", async () => {
    const transport = new RecordingTransport([
      jsonResponse({
        error: {
          code: "memory.bad_request",
          message: "bad Authorization: Bearer secret-token and ?api_key=abc",
          retryable: false,
        },
      }, 400),
    ]);
    const client = new InfinityContextClient({
      baseUrl: "http://memory.test",
      transport,
      retryPolicy: { maxAttempts: 1 },
    });

    try {
      await client.system.capabilities();
      throw new Error("expected capabilities to fail");
    } catch (error) {
      expect(error).toBeInstanceOf(InfinityContextError);
      const sdkError = error as InfinityContextError;
      expect(sdkError.code).toBe("memory.bad_request");
      expect(sdkError.message).toBe("bad Authorization: [REDACTED] and ?api_key=[REDACTED]");
      expect(sdkError.retryable).toBe(false);
    }
  });

  it("downloads byte responses without JSON parsing", async () => {
    const bytes = new Uint8Array([1, 2, 3]);
    const transport = new RecordingTransport([{ status: 200, headers: new Headers(), body: bytes }]);
    const client = new InfinityContextClient({
      baseUrl: "http://memory.test",
      transport,
      retryPolicy: { maxAttempts: 1 },
    });

    await expect(client.assets.downloadAsset("asset_1")).resolves.toEqual(bytes);
  });

  it("validates mixed canonical and external scopes", () => {
    expect(() =>
      MemoryScope.canonical({ spaceId: "space_1", memoryScopeId: "scope_1" }).toPayload(),
    ).not.toThrow();
    expect(() =>
      ReadScope.external({ spaceSlug: "workspace", memoryScopeExternalRef: "user:user_1" }).toPayload(),
    ).not.toThrow();
    expect(() =>
      new InfinityContextClient(),
    ).not.toThrow();
    expect(() =>
      MemoryScope.external({
        spaceSlug: "workspace",
        memoryScopeExternalRef: "scope",
      }).toPayload(),
    ).not.toThrow();
    const mixedInput = {
      spaceId: "space_1",
      memoryScopeId: "scope_1",
      spaceSlug: "workspace",
    } as unknown as Parameters<typeof MemoryScope.canonical>[0];
    expect(() => MemoryScope.canonical(mixedInput).toPayload()).toThrow(ValueError);
  });
});

function jsonResponse(body: unknown, status = 200): HttpResponse {
  return {
    status,
    headers: new Headers(),
    body: JSON.stringify(body),
  };
}
