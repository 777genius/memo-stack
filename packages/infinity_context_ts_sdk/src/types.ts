export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonObject | readonly JsonValue[];
export interface JsonObject {
  readonly [key: string]: JsonValue | undefined;
}

export type MaybePromise<T> = T | Promise<T>;

export type QueryParams = Record<string, unknown>;

export interface ApiEnvelope<T = JsonValue> {
  readonly data: T;
}

export interface SourceRef extends JsonObject {
  readonly source_type: string;
  readonly source_id: string;
}

export type Classification = "public" | "internal" | "confidential" | "restricted" | "unknown";

export interface Space {
  readonly id: string;
  readonly slug: string;
  readonly name: string;
  readonly status: string;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface MemoryScopeRecord {
  readonly id: string;
  readonly space_id: string;
  readonly external_ref: string;
  readonly name: string;
  readonly status: string;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface UserRecord {
  readonly id: string;
  readonly external_ref: string;
  readonly display_name: string;
  readonly email?: string | null;
  readonly status: string;
  readonly metadata: JsonObject;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface SpaceMembership {
  readonly id: string;
  readonly space_id: string;
  readonly user_id: string;
  readonly role: string;
  readonly status: string;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface FactRecord extends JsonObject {
  readonly id: string;
  readonly text: string;
  readonly kind: string;
  readonly status: string;
  readonly version: number;
}

export interface DocumentRecord extends JsonObject {
  readonly id: string;
  readonly title: string;
  readonly status: string;
}

export interface AssetRecord extends JsonObject {
  readonly id: string;
  readonly filename: string;
  readonly status: string;
}

export interface SuggestionRecord extends JsonObject {
  readonly id: string;
  readonly status: string;
  readonly candidate_text: string;
}

export interface AnchorRecord extends JsonObject {
  readonly id: string;
  readonly kind: string;
  readonly label: string;
  readonly status: string;
}

export interface InfinityContextHealth {
  readonly status: string;
  readonly service: string;
  readonly deploy_profile: string;
}

export interface InfinityContextCapabilities extends JsonObject {
  readonly api_version?: string;
  readonly server_version?: string;
  readonly service_name?: string;
  readonly deploy_profile?: string;
  readonly enabled_adapters?: string[];
  readonly supports_qdrant?: boolean;
  readonly supports_graphiti?: boolean;
}
