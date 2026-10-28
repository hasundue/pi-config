---
name: ketch
description: >
  Use the `ketch` CLI from `bash` for all external research — web pages, OSS
  code, and library docs. Activates when the user needs information that the
  agent cannot derive from its training data: current web pages, real-time
  search results, OSS code snippets with repository context, or library
  documentation. Also use when the user asks for research, lookups, source
  code from a specific repository, or library API details.
---

# Ketch CLI — External Research Tool

Use `ketch` CLI from `bash` for all external research — web pages, OSS code,
library docs. ketch is a fast, stateless CLI that provides three search surfaces
(web, code, docs) and scraping/crawling — one binary, no daemon.

## Prerequisites

The `ketch` CLI is already configured and installed. The operator has configured
the search/code/docs backends and browser. **Do not override or reconfigure**
**them** unless you have a specific reason.

To inspect the active configuration and available backends at any time:

```bash
ketch config
```

This returns the effective configuration as JSON — search backend, code backend,
docs backend, token sources, browser path, cache TTL, etc.

---

## Commands

### Web Search

Search the web and get titles, URLs, and snippets:

```bash
ketch search "<query>"
```

Search and fetch full content from each result in one pass:

```bash
ketch search "golang error handling" --scrape
```

Customize the number of results:

```bash
ketch search "query" --limit 10
```

Select a specific search backend (the default is configured by the operator):

```bash
ketch search "query" --backend ddg
ketch search "query" --backend searxng
# Supported backends: brave (default), ddg (zero config), searxng (self-hosted)
```

> **Rate limits — do not call in parallel.** The default `brave` backend is
> rate-limited (~1 request/second plus a monthly query quota). **Never issue
> multiple `ketch search` calls concurrently** — run them sequentially or space
> them out. If you get a `brave: rate limited` (HTTP 429) error, wait a moment
> and retry, or fall back with `--backend ddg`.

---

### Scrape a URL

Fetch a single URL and return clean markdown:

```bash
ketch scrape https://go.dev/doc/effective_go
```

**Batch scrape** — fetch multiple URLs concurrently:

```bash
ketch scrape https://example.com https://go.dev
```

Get raw HTML instead of markdown:

```bash
ketch scrape https://example.com --raw
```

Bypass the page cache to force a fresh fetch:

```bash
ketch scrape https://example.com --no-cache
```

---

### Crawl a Website

Crawl entire sites via BFS (breadth-first) link discovery or sitemaps:

```bash
# BFS crawl from a seed URL, default depth 3
ketch crawl https://example.com --depth 3
```

```bash
# Sitemap-based crawl (discovers pages from the sitemap)
ketch crawl https://example.com/sitemap.xml --sitemap
```

```bash
# Run in background with status tracking
ketch crawl https://example.com/sitemap.xml --sitemap --background
```

Control the crawl with additional options:

```bash
# Path substring filters (any match passes)
ketch crawl https://example.com --allow /docs,/api

# Regex deny patterns
ketch crawl https://example.com --deny "\.pdf$" --deny "/private/"

# Worker pool size
ketch crawl https://example.com --concurrency 8
```

Check crawl status or stop a running crawl:

```bash
ketch crawl status              # list all crawls
ketch crawl status c_a1b2c3d4   # check a specific crawl
ketch crawl stop c_a1b2c3d4     # stop a running crawl
```

Crawled pages are cached — re-running the same crawl returns instantly from
cache. Use `--no-cache` to force re-fetch.

---

### Code Search

Search real source code across open-source repositories with line numbers, repo
info, and star counts. Two backends are available:

**Sourcegraph** (default) — zero config, ~1M OSS repos, grep-style exact line
matches, archived/fork filters:

```bash
ketch code "http.NewRequestWithContext" --lang go
ketch code "rate limit middleware" --lang python
```

**GitHub Code Search** — uses the GitHub REST API with batched GraphQL stargazer
lookups. Authentication is resolved from (in order): explicit config →
`$GITHUB_TOKEN` → `$GH_TOKEN` → `gh auth token` (if `gh` CLI is installed):

```bash
ketch code "http.NewRequestWithContext" --lang go -b github
ketch code "rate limit middleware" --lang go -b github --limit 10
```

Each result shows: matched line, repository, file path, star count, and a
permalink. Results are filtered to non-archived, non-fork repos by default on
Sourcegraph.

---

### Library Docs

Fetch curated, version-aware documentation snippets via Context7:

```bash
# Auto-resolve the library from the query
ketch docs "middleware authentication"

# Fetch directly from a known library ID (skips resolution)
ketch docs "how to render with word wrap" --library /charmbracelet/glamour

# List matching library IDs without fetching docs
ketch docs --resolve "glamour"

# Control the token budget for results
ketch docs "middleware authentication" --tokens 6000
```

The operator has already configured the Context7 API key. Do not override it.

---

## JavaScript-Rendered Pages (Browser)

JS-rendered pages (React SPAs, Salesforce Lightning, etc.) are automatically
detected and re-fetched via headless Chrome. No special action is needed when
scraping or crawling — if a page returns a loading shell, ketch transparently
uses the browser.

If browser management is needed (e.g., to install Chromium or check status):

```bash
# Point ketch to an existing Chrome installation
ketch config set browser chrome

# Or install Chromium to ketch's cache dir
ketch browser install

# Check browser status
ketch browser status
```

Once configured, browser rendering is transparent — static pages are always
fetched via plain HTTP (fast path).

---

## Structured Output

All commands support `--json` for structured JSON output suitable for piping:

```bash
ketch search "<query>" --json
ketch code "<query>" --lang go --json
ketch scrape https://example.com --json
ketch config --json
```

---

## Configuration

The operator has already configured ketch. The configuration is stored at
`~/.config/ketch/config.json`. Flags always override config values.

To view the effective config and available backends:

```bash
ketch config
```

Example output:

```json
{
  "config_path": "/home/user/.config/ketch/config.json",
  "backend": "brave",
  "searxng_url": "http://localhost:8081",
  "limit": 5,
  "cache_ttl": "72h",
  "browser": "chrome",
  "available_backends": ["brave", "ddg", "searxng"]
}
```

### Search Backends

| Backend   | Setup                | Notes                                                                                                                          |
| --------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `brave`   | Free API key         | Stable JSON API (default). Rate-limited (~1 req/s + monthly quota) — avoid parallel calls; on 429 retry or fall back to `ddg`. |
| `ddg`     | Zero config          | Rate-limited by DDG currently                                                                                                  |
| `searxng` | Self-hosted instance | Most reliable for heavy use                                                                                                    |

### Code Backends

| Backend       | Setup                                                    | Notes                                                                               |
| ------------- | -------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `sourcegraph` | Zero config                                              | Grep-style, ~1M OSS repos, exact line matches                                       |
| `github`      | `gh auth login` or `ketch config set github_token <tok>` | REST `/search/code` + GraphQL stars batch, 30 req/min cap. Token needs `repo` scope |

### Docs Backends

| Backend    | Setup                                     | Notes                                             |
| ---------- | ----------------------------------------- | ------------------------------------------------- |
| `context7` | `ketch config set context7_api_key <key>` | Curated snippets + prose, version-aware (default) |
| `local`    | `ketch docs index <source>`               | FTS5 SQLite, offline/private docs (planned)       |

---

## Cache

ketch caches fetched pages and search results. Cache TTL defaults to 72h.

```bash
# Show cache stats
ketch cache

# Clear cached pages
ketch cache clear
```
