import type { MaybePromise } from "./types.js";

export type AuthTokenProvider =
  | string
  | null
  | undefined
  | (() => MaybePromise<string | null | undefined>)
  | { getToken: () => MaybePromise<string | null | undefined> };

export async function resolveAuthToken(provider: AuthTokenProvider): Promise<string | undefined> {
  const raw =
    typeof provider === "function"
      ? await provider()
      : typeof provider === "object" && provider !== null && "getToken" in provider
        ? await provider.getToken()
        : provider;

  const token = typeof raw === "string" ? raw.trim() : "";
  return token.length > 0 ? token : undefined;
}
