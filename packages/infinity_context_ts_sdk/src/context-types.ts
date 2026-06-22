import type { JsonObject, SourceRef } from "./types.js";

export interface ContextCitation extends JsonObject {
  readonly citation_id?: string;
  readonly label?: string;
  readonly source_type?: string;
  readonly source_id?: string;
  readonly chunk_id?: string | null;
  readonly quote_preview?: string | null;
  readonly retrieval_source?: string | null;
  readonly ranking_reason?: string | null;
}

export interface ContextItemDiagnostics extends JsonObject {
  readonly retrieval_source?: string | null;
  readonly retrieval_sources?: readonly string[];
  readonly ranking_reason?: string;
  readonly review_only?: boolean;
  readonly stale_reason?: string | null;
}

export interface ContextItem extends JsonObject {
  readonly item_id: string;
  readonly item_type: string;
  readonly memory_scope_id?: string | null;
  readonly text: string;
  readonly score: number;
  readonly source_refs: readonly SourceRef[];
  readonly citations?: readonly ContextCitation[];
  readonly is_instruction?: boolean;
  readonly diagnostics?: ContextItemDiagnostics;
}

export interface ContextEvidenceSelection extends JsonObject {
  readonly item?: ContextItem;
  readonly citation?: ContextCitation | null;
  readonly score?: number;
  readonly reasons?: readonly string[];
}

export interface ContextAnswerSupport extends JsonObject {
  readonly status: string;
  readonly items_returned: number;
  readonly coverage: JsonObject;
  readonly policy: JsonObject;
  readonly warnings: readonly string[];
}

export interface ContextDiagnostics extends JsonObject {
  readonly context_assembly_version?: string;
  readonly consistency_mode?: string;
  readonly vector_status?: string;
  readonly graph_status?: string;
  readonly rag_status?: string;
  readonly artifact_evidence_status?: string;
  readonly retrieval_sources_used?: readonly string[];
  readonly retrieval_sources_total?: number;
  readonly retrieval_sources_returned?: number;
  readonly items_considered?: number;
  readonly items_used?: number;
  readonly facts_considered?: number;
  readonly anchors_considered?: number;
  readonly keyword_chunks_considered?: number;
  readonly vector_candidate_count?: number;
  readonly vector_hydrated_count?: number;
  readonly graph_candidate_count?: number;
  readonly graph_hydrated_count?: number;
  readonly stale_vector_drop_count?: number;
  readonly stale_graph_drop_count?: number;
  readonly query_expansion_status?: string;
  readonly query_expansion_count?: number;
  readonly query_expansion_reasons?: readonly string[];
  readonly query_decomposition_status?: "empty" | "available" | string;
  readonly query_decomposition_count?: number;
  readonly query_decomposition_reasons?: readonly string[];
  readonly temporal_query_intent_status?: string;
  readonly temporal_query_prefers_current?: boolean;
  readonly temporal_query_requests_previous?: boolean;
  readonly temporal_query_requests_change?: boolean;
  readonly temporal_query_after_event?: boolean;
  readonly temporal_query_before_event?: boolean;
  readonly temporal_query_excludes_stale?: boolean;
  readonly temporal_query_include_superseded_review?: boolean;
}

export interface ContextBundleData extends JsonObject {
  readonly bundle_id: string;
  readonly rendered_text: string;
  readonly items: readonly ContextItem[];
  readonly top_evidence: readonly ContextEvidenceSelection[];
  readonly answer_support: ContextAnswerSupport;
  readonly diagnostics: ContextDiagnostics;
}

export interface SearchMemoryData extends JsonObject {
  readonly items: readonly ContextItem[];
  readonly top_evidence: readonly ContextEvidenceSelection[];
  readonly next_cursor?: string | null;
  readonly diagnostics: ContextDiagnostics;
}

export interface DigestSection extends JsonObject {
  readonly title: string;
  readonly items: readonly ContextItem[];
  readonly truncated: boolean;
}

export interface MemoryDigestData extends JsonObject {
  readonly digest_id: string;
  readonly topic: string;
  readonly rendered_markdown: string;
  readonly sections: readonly DigestSection[];
  readonly source_refs: readonly SourceRef[];
  readonly token_estimate: number;
  readonly diagnostics: JsonObject;
}

export interface ApiMeta extends JsonObject {
  readonly request_id?: string;
}

export interface ContextEnvelope<TData extends JsonObject> extends JsonObject {
  readonly meta?: ApiMeta;
  readonly data: TData;
}
