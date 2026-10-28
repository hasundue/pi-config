#!/usr/bin/env python3
"""Read PDFs: decide text vs OCR, extract text and tables, render page images.

Subcommands:
    info   FILE                 page count, metadata, and whether a text layer exists
    text   FILE                 extract text via pdftotext
    pages  FILE --out DIR       render pages to PNG/JPEG via pdftoppm
    tables FILE                 extract tables via pdfplumber (tsv or markdown)
    ocr    FILE                 render pages and run tesseract

Every subcommand accepts --pages (e.g. 1-5,8,12-). Output goes to stdout except
`pages`, which writes files and prints their paths. Exit status is 0 on success,
1 on a usage/processing error.

Run `pdf.py <subcommand> --help` for details.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PAGE_MARK = "--- page {n} ---"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def die(message: str) -> None:
    print(f"pdf.py: {message}", file=sys.stderr)
    raise SystemExit(1)


def page_count(pdf: Path) -> int:
    from pypdf import PdfReader

    try:
        return len(PdfReader(str(pdf)).pages)
    except Exception as exc:  # noqa: BLE001 - surface pypdf's message verbatim
        die(f"cannot read {pdf}: {exc}")
        return 0


def parse_pages(spec: str | None, total: int) -> list[int]:
    """Turn '1-5,8,12-' into a sorted list of 1-based page numbers."""
    if spec is None:
        return list(range(1, total + 1))
    pages: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_s, _, end_s = chunk.partition("-")
            start = int(start_s) if start_s.strip() else 1
            end = int(end_s) if end_s.strip() else total
        else:
            start = end = int(chunk)
        if start < 1 or end < start:
            die(f"bad page range {chunk!r}")
        if start > total:
            die(f"page {start} is out of range (file has {total} page(s))")
        pages.update(range(start, min(end, total) + 1))
    if not pages:
        die("no pages selected")
    return sorted(pages)


def runs(pages: list[int]) -> list[tuple[int, int]]:
    """Collapse 1-based page numbers into contiguous (first, last) runs."""
    out: list[tuple[int, int]] = []
    for page in pages:
        if out and page == out[-1][1] + 1:
            out[-1] = (out[-1][0], page)
        else:
            out.append((page, page))
    return out


def need(*binaries: str) -> None:
    missing = [b for b in binaries if shutil.which(b) is None]
    if missing:
        die(f"missing on PATH: {', '.join(missing)} (run verify-env.py)")


def run(argv: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        die(f"{argv[0]} failed ({proc.returncode}): {detail[0] if detail else 'no output'}")
    return proc


# --------------------------------------------------------------------------- #
# subcommands
# --------------------------------------------------------------------------- #
def cmd_info(args: argparse.Namespace) -> int:
    pdf = args.file
    total = page_count(pdf)
    probe = min(total, 3)

    import pdfplumber

    chars_per_page: list[int] = []
    with pdfplumber.open(str(pdf)) as doc:
        for page in doc.pages[:probe]:
            chars_per_page.append(len((page.extract_text() or "").strip()))
    # Scans yield ~0 characters; ordinary documents yield tens per page. Keep the
    # bar low so short one-page files (e.g. a single sentence) still count.
    text_layer = sum(chars_per_page) >= 10 * probe

    info: dict[str, object] = {
        "file": str(pdf),
        "pages": total,
        "text_layer": text_layer,
        "chars_on_first_pages": chars_per_page,
        "recommendation": "text" if text_layer else "ocr",
    }
    if shutil.which("pdfinfo"):
        proc = subprocess.run(
            ["pdfinfo", str(pdf)], capture_output=True, text=True, check=False
        )
        for line in proc.stdout.splitlines():
            key, _, value = line.partition(":")
            if key.strip() in {"Title", "Author", "Producer", "Creator", "Page size", "Encrypted"}:
                info[key.strip().lower().replace(" ", "_")] = value.strip()

    if args.json:
        print(json.dumps(info, indent=2))
    else:
        for key, value in info.items():
            print(f"{key:<22} {value}")
        if not text_layer:
            print("\nNo usable text layer: use `ocr` (text extraction would return little).")
    return 0


def cmd_text(args: argparse.Namespace) -> int:
    need("pdftotext")
    pdf = args.file
    pages = parse_pages(args.pages, page_count(pdf))
    chunks: list[str] = []
    for first, last in runs(pages):
        proc = run(
            [
                "pdftotext",
                f"-{args.mode}",
                "-enc",
                "UTF-8",
                "-f",
                str(first),
                "-l",
                str(last),
                str(pdf),
                "-",
            ]
        )
        body = proc.stdout.strip()
        if len(pages) > 1:
            body = f"{PAGE_MARK.format(n=first if first == last else f'{first}-{last}')}\n{body}"
        chunks.append(body)
    text = "\n\n".join(chunk for chunk in chunks if chunk)
    if not text.strip():
        die("pdftotext produced no text; the pages are probably scanned (use `ocr`)")
    if len(text.strip()) < 40:
        print(
            "note: very little text came out; if you expected more, the pages are "
            "probably scanned (use `ocr`)",
            file=sys.stderr,
        )
    print(trim(text, args.max_chars))
    return 0


def cmd_pages(args: argparse.Namespace) -> int:
    need("pdftoppm")
    pdf = args.file
    pages = parse_pages(args.pages, page_count(pdf))
    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for first, last in runs(pages):
        run(
            [
                "pdftoppm",
                f"-{args.format}",
                "-r",
                str(args.dpi),
                "-f",
                str(first),
                "-l",
                str(last),
                str(pdf),
                str(out_dir / pdf.stem),
            ]
        )
    # pdftoppm appends the page number, so one glob covers every run
    written = sorted(
        out_dir.glob(f"{pdf.stem}-*.{args.format}"),
        key=lambda p: int(p.stem.rsplit("-", 1)[-1]) if p.stem.rsplit("-", 1)[-1].isdigit() else 0,
    )
    if not written:
        die("pdftoppm produced no images")
    for path in written:
        print(path)
    return 0


def cmd_tables(args: argparse.Namespace) -> int:
    pdf = args.file
    pages = parse_pages(args.pages, page_count(pdf))

    import pdfplumber

    found = 0
    # "lines" needs ruling lines; "text" infers columns from aligned whitespace,
    # which is what most papers and reports actually use.
    settings = (
        {"vertical_strategy": "text", "horizontal_strategy": "text"}
        if args.strategy == "text"
        else {}
    )
    with pdfplumber.open(str(pdf)) as doc:
        for number in pages:
            if number > len(doc.pages):
                break
            groups = doc.pages[number - 1].extract_tables(table_settings=settings)
            for index, rows in enumerate(groups, 1):
                found += 1
                if args.format == "md":
                    print(f"### page {number}, table {index}")
                    print(markdown_table(rows))
                    print()
                else:
                    for row in rows:
                        cells = [(cell or "").replace("\t", " ").replace("\n", " ") for cell in row]
                        print(f"{number}\t{index}\t" + "\t".join(cells))
    if not found:
        hint = "--strategy text" if args.strategy == "lines" else "`text`"
        print(
            f"no tables detected on pages {pages[0]}-{pages[-1]} "
            f"(retry with {hint}, or read the layout instead)",
            file=sys.stderr,
        )
        return 1
    return 0


def cmd_ocr(args: argparse.Namespace) -> int:
    need("pdftoppm", "tesseract")
    pdf = args.file
    pages = parse_pages(args.pages, page_count(pdf))
    total_chars = 0
    with tempfile.TemporaryDirectory(prefix="pdf-ocr-") as tmp:
        for number in pages:
            prefix = Path(tmp) / f"page-{number}"
            run(
                [
                    "pdftoppm",
                    "-png",
                    "-r",
                    str(args.dpi),
                    "-f",
                    str(number),
                    "-l",
                    str(number),
                    str(pdf),
                    str(prefix),
                ]
            )
            images = sorted(Path(tmp).glob(f"page-{number}-*.png")) or sorted(
                Path(tmp).glob(f"page-{number}.png")
            )
            if not images:
                die(f"pdftoppm produced no image for page {number}")
            proc = run(["tesseract", str(images[0]), "-", "-l", args.lang], timeout=600)
            body = proc.stdout.strip()
            total_chars += len(body)
            print(PAGE_MARK.format(n=number))
            print(body)
            print()
    if total_chars == 0:
        print(
            f"warning: OCR returned no text (lang={args.lang}); the page may be empty "
            "or the language data may be missing",
            file=sys.stderr,
        )
    return 0


# --------------------------------------------------------------------------- #
# formatting
# --------------------------------------------------------------------------- #
def trim(text: str, limit: int | None) -> str:
    if limit is None or len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[... truncated at {limit} characters]"


def markdown_table(rows: list[list[str | None]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    grid = [[(cell or "").replace("\n", " ").strip() for cell in row] for row in rows]
    for row in grid:
        row.extend([""] * (width - len(row)))
    header, *body = grid
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_file(p: argparse.ArgumentParser) -> None:
        p.add_argument("file", type=Path, help="PDF path")

    def add_pages(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--pages",
            help="1-based page selection: 3, 1-5, 10-, or 1-3,7 (default: all pages)",
        )

    p = sub.add_parser("info", help="page count, metadata, text-layer detection")
    add_file(p)
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("text", help="extract text with pdftotext")
    add_file(p)
    add_pages(p)
    p.add_argument(
        "--mode",
        choices=("layout", "raw"),
        default="layout",
        help="layout keeps columns (default); raw keeps content-stream order",
    )
    p.add_argument("--max-chars", type=int, help="truncate output")
    p.set_defaults(func=cmd_text)

    p = sub.add_parser("pages", help="render pages to images with pdftoppm")
    add_file(p)
    add_pages(p)
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--dpi", type=int, default=150)
    p.add_argument("--format", choices=("png", "jpeg"), default="png")
    p.set_defaults(func=cmd_pages)

    p = sub.add_parser("tables", help="extract tables with pdfplumber")
    add_file(p)
    add_pages(p)
    p.add_argument("--format", choices=("tsv", "md"), default="tsv")
    p.add_argument(
        "--strategy",
        choices=("lines", "text"),
        default="lines",
        help="lines: rely on ruling lines (default); text: infer columns from whitespace",
    )
    p.set_defaults(func=cmd_tables)

    p = sub.add_parser("ocr", help="render pages and OCR them with tesseract")
    add_file(p)
    add_pages(p)
    p.add_argument("--lang", default="eng", help="tesseract language (default: eng)")
    p.add_argument("--dpi", type=int, default=300, help="render resolution (default: 300)")
    p.set_defaults(func=cmd_ocr)

    args = parser.parse_args()
    if not args.file.is_file():
        die(f"no such file: {args.file}")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
