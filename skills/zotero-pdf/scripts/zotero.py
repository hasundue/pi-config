#!/usr/bin/env python3
"""Find a paper in Zotero and resolve its local PDF, using Zotero's local API.

Subcommands:
    search QUERY       list matching items with their keys and PDF availability
    attachments ITEM   list the attachments of an item
    path ITEM          print the local PDF path (ITEM may be an item or attachment)
    info ITEM          metadata and abstract

Zotero 7 must be running with "Allow other applications on this computer to
communicate with Zotero" enabled; the API is read-only.

Environment:
    ZOTERO_API   base URL (default http://127.0.0.1:23119/api/users/0)

Exit status: 0 on success, 1 when Zotero is unreachable, the item is missing, or
no PDF attachment exists.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_API = "http://127.0.0.1:23119/api/users/0"
TIMEOUT = 15


def api_base() -> str:
    return os.environ.get("ZOTERO_API", DEFAULT_API).rstrip("/")


def die(message: str) -> None:
    print(f"zotero.py: {message}", file=sys.stderr)
    raise SystemExit(1)


def get(path: str) -> dict | list:
    url = f"{api_base()}/{path.lstrip('/')}"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            die(f"not found: {path}")
        die(f"Zotero API returned HTTP {exc.code} for {url}")
    except urllib.error.URLError as exc:
        die(
            f"cannot reach Zotero at {api_base()} ({exc.reason}); start Zotero and "
            "enable Settings → Advanced → 'Allow other applications on this "
            "computer to communicate with Zotero'"
        )
    return {}


def item(key: str) -> dict:
    data = get(f"items/{key}")
    if not isinstance(data, dict):
        die(f"unexpected response for item {key}")
    return data


def children(key: str) -> list[dict]:
    data = get(f"items/{key}/children")
    return data if isinstance(data, list) else []


def is_pdf(entry: dict) -> bool:
    meta = entry.get("data", {})
    content_type = (meta.get("contentType") or "").lower()
    if "pdf" in content_type:
        return True
    name = meta.get("filename") or meta.get("title") or ""
    return str(name).lower().endswith(".pdf")


def enclosure_path(entry: dict) -> Path | None:
    href = (entry.get("links", {}).get("enclosure", {}) or {}).get("href")
    if not href:
        return None
    raw = href[len("file://") :] if href.startswith("file://") else href
    return Path(urllib.parse.unquote(raw))


def pdf_of(entry: dict) -> tuple[Path | None, str]:
    """Resolve the PDF file for an item or attachment entry."""
    key = entry.get("key", "?")
    meta = entry.get("data", {})
    if meta.get("itemType") == "attachment":
        if not is_pdf(entry):
            return None, f"{key} is an attachment but not a PDF ({meta.get('contentType')})"
        return enclosure_path(entry), key
    for child in children(key):
        if child.get("data", {}).get("itemType") == "attachment" and is_pdf(child):
            return enclosure_path(child), child.get("key", "?")
    return None, f"{key} has no PDF attachment"


def year_of(meta: dict) -> str:
    match = re.search(r"\d{4}", str(meta.get("date") or ""))
    return match.group(0) if match else "n.d."


def first_author(meta: dict) -> str:
    creators = meta.get("creators") or []
    for creator in creators:
        name = creator.get("lastName") or creator.get("name")
        if name:
            return str(name)
    return "?"


def cmd_search(args: argparse.Namespace) -> int:
    query = urllib.parse.quote(args.query)
    # Zotero matches attachment titles too, and the limit applies before we can
    # drop them, so fetch a wider window than the caller asked for.
    window = max(args.limit * 4, 20)
    params = f"items?q={query}&limit={window}"
    if args.mode:
        params += f"&qmode={args.mode}"
    results = get(params)
    if not isinstance(results, list):
        die("unexpected search response")

    rows: list[dict] = []
    seen: set[str] = set()
    parents: list[str] = []
    for entry in results:
        meta = entry.get("data", {})
        key = entry.get("key", "")
        if meta.get("itemType") == "attachment":
            # remember the parent so a query that only hits attachment titles
            # ("PDF", "APS Snapshot") can still resolve to the paper
            parent = meta.get("parentItem")
            if parent and parent not in parents:
                parents.append(parent)
            continue
        if key and key not in seen:
            seen.add(key)
            rows.append(entry)

    if not rows and parents:
        for parent in parents[: args.limit]:
            entry = item(parent)
            key = entry.get("key", "")
            if key and key not in seen:
                seen.add(key)
                rows.append(entry)

    rows = rows[: args.limit]
    if not rows:
        print("no matching items", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps([{"key": r["key"], **r["data"]} for r in rows], indent=2))
        return 0
    for entry in rows:
        meta = entry["data"]
        print(
            f"{entry['key']}  {year_of(meta):<4}  {meta.get('itemType', '?'):<13}  "
            f"{first_author(meta):<16}  {(meta.get('title') or 'untitled')[:80]}"
        )
    return 0


def cmd_attachments(args: argparse.Namespace) -> int:
    entry = item(args.item)
    listing = (
        [entry]
        if entry.get("data", {}).get("itemType") == "attachment"
        else children(args.item)
    )
    if not listing:
        print("no attachments", file=sys.stderr)
        return 1
    for child in listing:
        meta = child.get("data", {})
        path = enclosure_path(child)
        print(
            f"{child.get('key', '?'):8}  {meta.get('contentType') or '?':<16}  "
            f"{path if path else '(no local file)'}"
        )
    return 0


def slugify(text: str, limit: int = 60) -> str:
    text = re.sub(r"[^\w\s.-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:limit].strip("._") or "paper"


def cmd_path(args: argparse.Namespace) -> int:
    entry = item(args.item)
    path, source = pdf_of(entry)
    if path is None:
        die(source)
    if not path.exists():
        die(f"{source} points at {path}, which does not exist (is the file on disk?)")
    if not args.copy_to:
        print(path)
        return 0

    meta = entry.get("data", {})
    if meta.get("itemType") == "attachment":
        name = meta.get("filename") or path.name
    else:
        name = f"{year_of(meta)}_{first_author(meta)}_{meta.get('title') or path.stem}"
    target = Path(args.copy_to).expanduser() / (slugify(name) + ".pdf")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    print(target)
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    entry = item(args.item)
    meta = entry.get("data", {})
    if args.json:
        print(json.dumps({"key": entry.get("key"), **meta}, indent=2))
        return 0
    authors = ", ".join(
        f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
        or c.get("name", "")
        for c in meta.get("creators") or []
    )
    fields = [
        ("key", entry.get("key")),
        ("type", meta.get("itemType")),
        ("title", meta.get("title")),
        ("authors", authors),
        ("date", meta.get("date")),
        ("publication", meta.get("publicationTitle") or meta.get("proceedingsTitle")),
        ("volume", meta.get("volume")),
        ("pages", meta.get("pages")),
        ("doi", meta.get("DOI")),
        ("url", meta.get("url")),
    ]
    for label, value in fields:
        if value:
            print(f"{label:<12} {value}")
    abstract = (meta.get("abstractNote") or "").strip()
    if abstract:
        print(f"\n{abstract}\n")
    path, source = pdf_of(entry)
    if path is None:
        print(f"pdf          none ({source})")
    else:
        state = "ok" if path.exists() else "MISSING ON DISK"
        print(f"pdf          {path} [{source}, {state}]")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("search", help="search the library")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument(
        "--mode",
        choices=("titleCreatorYear", "everything"),
        default="everything",
        help="Zotero search mode (default: everything)",
    )
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("attachments", help="list an item's attachments")
    p.add_argument("item", help="item key")
    p.set_defaults(func=cmd_attachments)

    p = sub.add_parser("path", help="print the local PDF path")
    p.add_argument("item", help="item key (journal article) or attachment key")
    p.add_argument(
        "--copy-to",
        metavar="DIR",
        help="copy the PDF into DIR under a clean file name and print that path",
    )
    p.set_defaults(func=cmd_path)

    p = sub.add_parser("info", help="show metadata, abstract, and PDF status")
    p.add_argument("item", help="item key")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_info)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
