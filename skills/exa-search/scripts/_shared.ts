/**
 * Shared utilities for Exa search and fetch scripts.
 *
 * Environment:
 *   EXA_API_KEY       — the API key directly (takes precedence)
 *   EXA_API_KEY_FILE  — path to a file containing the API key (fallback)
 */

import { Exa } from "npm:exa-js@2.12.1";

/** Read the API key from environment. Exits with an error if missing. */
export function getApiKey(): string {
  const direct = Deno.env.get("EXA_API_KEY");
  if (direct) return direct;

  const keyFile = Deno.env.get("EXA_API_KEY_FILE");
  if (keyFile) {
    try {
      return Deno.readTextFileSync(keyFile).trim();
    } catch {
      console.error(`Error: could not read EXA_API_KEY_FILE: ${keyFile}`);
      Deno.exit(1);
    }
  }

  console.error("Error: neither EXA_API_KEY nor EXA_API_KEY_FILE is set.");
  console.error(
    "Set EXA_API_KEY directly, or point EXA_API_KEY_FILE at a file containing the key.",
  );
  Deno.exit(1);
}

/** Get an API key and create an Exa client. Exits on missing/empty key. */
export function createExa(): Exa {
  const apiKey = getApiKey();
  if (!apiKey) {
    console.error("Error: API key is empty.");
    console.error(
      "Check the content of EXA_API_KEY_FILE or the value of EXA_API_KEY.",
    );
    Deno.exit(1);
  }
  return new Exa(apiKey);
}

/**
 * Strip verbose fields and empty highlightScores from the response,
 * unless `verbose` is true.
 */
export function minifyResponse(data: unknown, verbose: boolean): unknown {
  if (Array.isArray(data)) {
    return data.map((item) => minifyResponse(item, verbose));
  }
  if (data && typeof data === "object") {
    const obj = data as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(obj)) {
      if (k === "highlightScores" && Array.isArray(v) && v.length === 0) {
        continue;
      }
      if (!verbose && (k === "requestId" || k === "resolvedSearchType")) {
        continue;
      }
      out[k] = minifyResponse(v, verbose);
    }
    return out;
  }
  return data;
}

/** Common error handler for Exa API calls. */
export function handleExaError(err: unknown): never {
  console.error(
    "Exa API error:",
    err instanceof Error ? err.message : String(err),
  );
  Deno.exit(1);
}
