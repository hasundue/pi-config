#!/usr/bin/env python3
"""Verify that every PDF tool shipped through pi's extraPackages is callable.

Checks, in order:
  1. CLI binaries resolve on PATH and report a version
  2. Python modules import and report a version
  3. End-to-end smoke test: PDF -> PNG (pdf2image/poppler) -> OCR (tesseract)

Usage:
    python3 verify-env.py            # full check
    python3 verify-env.py --no-smoke # binaries and imports only
    python3 verify-env.py --pdf FILE # smoke test a real PDF instead of a blank one

Exit status: 0 when everything works, 1 when anything is missing or broken.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BINARIES = {
    "pdftoppm": "-v",  # poppler tools take -v, not --version
    "pdftotext": "-v",
    "pdfinfo": "-v",
    "qpdf": "--version",
    "tesseract": "--version",
}

# import name -> distribution name (for version lookup)
MODULES = {
    "pypdf": "pypdf",
    "pdfplumber": "pdfplumber",
    "pdf2image": "pdf2image",
    "pytesseract": "pytesseract",
    "PIL": "pillow",
}

WIDTH = 16
failures: list[str] = []


def row(label: str, detail: str) -> None:
    print(f"  {label:<{WIDTH}} {detail}")


def problem(label: str, detail: str) -> None:
    failures.append(label)
    row(label, f"FAIL  {detail}")


def check_binaries() -> None:
    print("== binaries ==")
    for name, flag in BINARIES.items():
        path = shutil.which(name)
        if path is None:
            problem(name, "not on PATH")
            continue
        try:
            proc = subprocess.run(
                [name, flag],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            problem(name, f"{path} (version check failed: {exc})")
            continue
        # banners go to stdout for most tools, to stderr for poppler on some builds
        lines = [ln.strip() for ln in (proc.stdout + proc.stderr).splitlines() if ln.strip()]
        version = lines[0] if lines else "?"
        row(name, f"{path}  [{version}]")


def check_modules() -> None:
    print("== python ==")
    for module, dist in MODULES.items():
        try:
            importlib.import_module(module)
            version = importlib.metadata.version(dist)
        except ImportError:
            problem(dist, "not importable")
            continue
        except importlib.metadata.PackageNotFoundError:
            version = "?"
        row(dist, version)


def make_blank_pdf(path: Path) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=100)
    with path.open("wb") as fh:
        writer.write(fh)


def check_end_to_end(pdf: Path, generated: bool) -> None:
    print(f"== end-to-end (PDF -> PNG -> OCR): {pdf.name} ==")
    if generated:
        row("pypdf", f"wrote {pdf.name} ({pdf.stat().st_size} bytes)")
    from pdf2image import convert_from_path

    pages = convert_from_path(str(pdf), dpi=150)
    if not pages:
        problem("pdf2image", "rendered no pages")
        return
    first = pages[0]
    out = pdf.with_name("page-1.png")
    first.save(out)
    row("pdf2image", f"{len(pages)} page(s) -> {out.name} {first.size}")

    result = subprocess.run(
        ["tesseract", str(out), "-"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        problem("tesseract", result.stderr.strip().splitlines()[-1:] or "failed")
        return
    rows = len([line for line in result.stdout.splitlines() if line.strip()])
    row("tesseract", f"OCR ok ({rows} text line(s))")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-smoke", action="store_true", help="skip the end-to-end test")
    parser.add_argument("--pdf", type=Path, help="smoke test this PDF instead of a blank one")
    args = parser.parse_args()

    check_binaries()
    check_modules()

    if not args.no_smoke:
        with tempfile.TemporaryDirectory(prefix="pdf-tools-") as tmp:
            if args.pdf:
                source = args.pdf.expanduser().resolve()
                generated = False
                if not source.is_file():
                    problem("--pdf", f"{source} not found")
                    source = None
            else:
                source = Path(tmp) / "blank.pdf"
                generated = True
                make_blank_pdf(source)
            if source is not None:
                check_end_to_end(source, generated)

    print()
    if failures:
        print("RESULT: FAIL — not callable: " + ", ".join(failures))
        print("Fix: add the missing package to extraPackages in dotnix/configs/home/pi.nix,")
        print("     rebuild (nix run .#home-build), switch (nix run .#home-switch), restart pi.")
        return 1
    print("RESULT: OK — all PDF tooling is callable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
