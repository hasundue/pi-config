#!/usr/bin/env -S deno run --allow-net --allow-env=EXA_API_KEY,EXA_API_KEY_FILE --allow-read

/**
 * Exa Fetch — URL content extraction via the Exa API /contents endpoint.
 *
 * Usage:
 *   ./scripts/fetch.ts https://example.com/article
 *   ./scripts/fetch.ts https://example.com/a https://example.com/b
 *   ./scripts/fetch.ts https://example.com --max-age-hours 24 --text --max-chars 5000
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
  boolean: ["highlights", "no-highlights", "text", "verbose"],
  string: ["max-chars", "max-age-hours"],
});

const urls = parsed._.map(String).filter(Boolean);

if (urls.length === 0) {
  console.error("Error: Provide at least one URL to fetch.");
  console.error("Run with --help to see usage.");
  Deno.exit(1);
}

const highlights = parsed["no-highlights"]
  ? false
  : (parsed.highlights ?? true);
const text = parsed.text ?? false;
const maxChars = parsed["max-chars"]
  ? parseInt(parsed["max-chars"] as string, 10)
  : 2000;
const maxAgeHours = parsed["max-age-hours"]
  ? parseInt(parsed["max-age-hours"] as string, 10)
  : undefined;
const verbose = parsed.verbose ?? false;

// Handle --help
if (Deno.args.includes("--help") || Deno.args.includes("-h")) {
  console.log(`
Usage:
  ./scripts/fetch.ts <url>... [options]

Arguments:
  url(s)                    One or more URLs to fetch content from

Options:
  --highlights [true|false] Include query-relevant excerpts (default: on)
  --no-highlights           Disable highlights
  --text                    Include full page text
  --max-chars <n>           Max characters when --text is set (default: 2000)
  --max-age-hours <n>       Max cache age in hours (0 = livecrawl, -1 = cache only)
  --verbose                 Include verbose fields
`);
  Deno.exit(0);
}

// --- Build options ---
const options: Record<string, unknown> = {};

if (highlights) options.highlights = true;
if (text) {
  options.text = {
    maxCharacters: maxChars,
    includeHtmlTags: false,
  };
}
if (maxAgeHours !== undefined) {
  options.maxAgeHours = maxAgeHours;
}

// --- Execute ---
async function main() {
  const results = await exa.getContents(urls, options);
  console.log(JSON.stringify(minifyResponse(results, verbose), null, 2));
}

try {
  await main();
} catch (err) {
  handleExaError(err);
}
