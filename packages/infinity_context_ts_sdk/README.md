# @infinity-context/sdk

TypeScript SDK for the Infinity Context memory API.

The SDK is intentionally HTTP-first. Qdrant, Graphiti, OpenAI embeddings and Postgres stay behind the Infinity Context service boundary; Node/Nest clients should depend on this SDK contract instead of importing server adapters directly.

## Install

```bash
npm install @infinity-context/sdk
```

## Usage

```ts
import { InfinityContextClient, ReadScope } from "@infinity-context/sdk";

const memory = new InfinityContextClient({
  baseUrl: process.env.INFINITY_CONTEXT_URL ?? "http://127.0.0.1:7788",
  token: () => process.env.INFINITY_CONTEXT_TOKEN,
});

const space = await memory.spaces.createSpace({
  slug: "social-monitor:tenant_1:workspace_1",
  name: "Social Monitor workspace",
});

await memory.facts.rememberFact({
  spaceSlug: "social-monitor:tenant_1:workspace_1",
  memoryScopeExternalRef: "topic:ai-agents:feedback",
  text: "User prefers concise daily AI agent summaries with links to primary sources.",
  kind: "preference",
  sourceRefs: [{ source_type: "social-monitor", source_id: "feedback:1" }],
  idempotencyKey: "feedback:1",
});

const context = await memory.context.buildContext({
  query: "What should the next AI agents digest prioritize?",
  readScope: ReadScope.external({
    spaceSlug: "social-monitor:tenant_1:workspace_1",
    memoryScopeExternalRefs: ["workspace-global", "user:user_1", "topic:ai-agents:feedback"],
  }),
  tokenBudget: 1800,
  maxFacts: 20,
  maxChunks: 30,
});

console.log(context.data);
```

## Recommended Social Monitor mapping

- `spaceSlug`: `social-monitor:{tenantId}:{workspaceId}`
- workspace memory scope: `workspace-global`
- user preference scope: `user:{userId}`
- topic preference scope: `topic:{topicId}:preferences`
- topic feedback scope: `topic:{topicId}:feedback`
- source scope: `source:{sourceBindingId}`

Keep operational state in Social Monitor Postgres. Store only reusable semantic memory, preferences, feedback lessons, topic ranking hints and digest style in Infinity Context.

## Full memory mode

To exercise the full memory stack, run Infinity Context with Postgres + Qdrant + Neo4j/Graphiti + OpenAI embeddings. The SDK does not change between lite and full profiles; the service capability payload should show healthy `qdrant` and `graphiti` adapters.

```ts
const capabilities = await memory.system.capabilities();

if (!capabilities.enabled_adapters?.includes("qdrant")) {
  throw new Error("Expected full memory mode with qdrant enabled");
}
```

For beta-grade proof, run a loop that writes feedback, builds context, ingests documents or episodes, verifies vector/graph diagnostics, then builds a digest from the same scopes.
