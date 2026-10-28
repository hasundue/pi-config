#!/usr/bin/env -S deno run --allow-net --allow-env=EXA_API_KEY,EXA_API_KEY_FILE --allow-read

/**
 * Exa Search — Deno helper using the official exa-js SDK.
 *
 * Usage:
 *   ./scripts/search.ts "query"
 *   ./scripts/search.ts "query" --num-results 5 --type deep
 *   ./scripts/search.ts "query" --schema '{ "type": "object", ... }'
 *
 * Environment:
 *   EXA_API_KEY       — the API key directly (takes precedence)
 *   EXA_API_KEY_FILE  — path to a file containing the API key (fallback)
 */

import { parseArgs } from "jsr:@std/cli@1.0.17/parse-args";
import { createExa, handleExaError, minifyResponse } from "./_shared.ts";

const exa = createExa();

// --- Argument parsing ---
const parsed = parseArgs(Deno.args, {
  boolean: ["verbose", "text", "summary", "highlights", "no-highlights"],
  string: [
    "type",
    "num-results",
    "max-chars",
    "max-age-hours",
    "start-published-date",
    "end-published-date",
    "include-domains",
    "exclude-domains",
    "schema",
  ],
});

const query = parsed._.join(" ");

if (!query) {
  console.error("Error: Provide a search query.");
  console.error("Run with --help to see usage.");
  Deno.exit(1);
}

const verbose = parsed.verbose ?? false;
const text = parsed.text ?? false;
const summary = parsed.summary ?? false;
const numResults = parsed["num-results"]
  ? parseInt(parsed["num-results"] as string, 10)
  : undefined;
const maxChars = parsed["max-chars"]
  ? parseInt(parsed["max-chars"] as string, 10)
  : undefined;
const searchType = parsed.type ?? "auto";
const maxAgeHours = parsed["max-age-hours"]
  ? parseInt(parsed["max-age-hours"] as string, 10)
  : undefined;
const startDate = parsed["start-published-date"];
const endDate = parsed["end-published-date"];

const includeDomains = parsed["include-domains"]
  ? (parsed["include-domains"] as string).split(",").map((s) => s.trim())
    .filter(Boolean)
  : undefined;
const excludeDomains = parsed["exclude-domains"]
  ? (parsed["exclude-domains"] as string).split(",").map((s) => s.trim())
    .filter(Boolean)
  : undefined;

const highlights = parsed["no-highlights"]
  ? false
  : (parsed.highlights ?? true);

let schema: Record<string, unknown> | undefined;
if (parsed.schema) {
  try {
    schema = JSON.parse(parsed.schema as string);
  } catch {
    console.error("Error: --schema must be valid JSON.");
    Deno.exit(1);
  }
}

// Handle --help
if (Deno.args.includes("--help") || Deno.args.includes("-h")) {
  console.log(`
Usage:
  ./scripts/search.ts "query" [options]

Options:
  --num-results <n>         Number of results (default: 10)
  --type <type>             Search type: auto, fast, instant, deep-lite, deep, deep-reasoning (default: auto)
  --highlights [true|false] Include query-relevant excerpts (default: on)
  --no-highlights           Disable highlights
  --text                    Include full page text
  --max-chars <n>           Max characters when --text is set (default: 2000)
  --summary                 Include per-result summaries
  --verbose                 Include verbose fields (requestId, resolvedSearchType)
  --schema <json>           JSON Schema for structured output (outputSchema)

Filtering:
  --include-domains <list>  Comma-separated domains to include
  --exclude-domains <list>  Comma-separated domains to exclude
  --start-published-date <d> ISO date (e.g. 2024-01-01)
  --end-published-date <d>   ISO date
  --max-age-hours <n>       Max cache age in hours (0 = livecrawl, -1 = cache only)
`);
  Deno.exit(0);
}

// --- Build search params ---
function buildSearchParams(): Record<string, unknown> {
  const params: Record<string, unknown> = {
    numResults: numResults ?? 10,
    type: searchType,
  };

  const contents: Record<string, unknown> = {};

  if (highlights) contents.highlights = true;
  if (text) {
    contents.text = {
      maxCharacters: maxChars ?? 2000,
      includeHtmlTags: false,
    };
  }
  if (summary) contents.summary = true;

  if (Object.keys(contents).length > 0) {
    params.contents = contents;
  }

  if (schema) {
    params.outputSchema = schema;
  }

  if (includeDomains) params.includeDomains = includeDomains;
  if (excludeDomains) params.excludeDomains = excludeDomains;
  if (startDate) params.startPublishedDate = startDate;
  if (endDate) params.endPublishedDate = endDate;
  if (maxAgeHours !== undefined) params.maxAgeHours = maxAgeHours;

  return params;
}

// --- Execute ---
async function main() {
  const params = buildSearchParams();
  const results = await exa.search(query, params);
  console.log(JSON.stringify(minifyResponse(results, verbose), null, 2));
}

try {
  await main();
} catch (err) {
  handleExaError(err);
}
