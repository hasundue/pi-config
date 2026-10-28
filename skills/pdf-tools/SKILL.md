---
name: pdf-tools
description: >
  Read the contents of PDF files: extract text and tables, render pages to
  images for visual inspection of figures, and OCR scanned (image-only) PDFs.
  Use when a task needs a local PDF, when ketch's built-in extraction returns
  garbage or empty output (scanned pages), or when a chart, diagram, or table
  layout must actually be seen rather than guessed from captions.
---

# PDF Tools

Tooling for reading PDFs comes from Nix (`dotnix/configs/home/pi.nix`,
`programs.pi-coding-agent.extraPackages`), so it is on `PATH` for this agent and
its `bash` tool — nothing needs installing at runtime.

## Verify the environment first

```bash
bash ~/.pi/agent/skills/pdf-tools/scripts/verify-env.sh
```

The script checks every binary and Python import, runs an end-to-end smoke test
(PDF → PNG → OCR) in a temp dir, and exits non-zero listing what is missing.
Run it once per session before trusting the rest of this skill.

## Route by input, not by habit

| Situation | Do this |
| --- | --- |
| PDF behind a URL, text layer intact | `ketch scrape <url>` — built-in extraction, no OCR, cheapest |
| Local PDF, text layer intact | `pdftotext -layout doc.pdf -` (or `pdfplumber` for tables) |
| **Scanned** PDF (image-only), or ketch returns 6 tokens of noise | **OCR**: `tesseract` / `pytesseract` (see below) |
| Figures, charts, multi-column layout matter | `pdftoppm` → PNG → `read` each page image (vision) |
| Tables | `pdfplumber` `extract_tables()` — keeps rows/columns that text extraction destroys |
| Split / merge / rotate / decrypt | `qpdf` |

## Commands

Text and metadata:

```bash
pdfinfo doc.pdf
pdftotext -layout doc.pdf -            # layout preserved, best for prose
pdftotext -f 3 -l 5 doc.pdf -          # page range only
```

Pages to images (for `read` / vision). Render only the pages you need — every
page image is a separate attachment and costs context:

```bash
pdftoppm -png -r 150 -f 1 -l 4 doc.pdf /tmp/doc   # -> /tmp/doc-1.png ...
```

Tables:

```bash
python3 - <<'PY'
import pdfplumber
with pdfplumber.open("doc.pdf") as pdf:
    for i, page in enumerate(pdf.pages, 1):
        for table in page.extract_tables():
            print(f"--- page {i} ---")
            for row in table:
                print(" | ".join(c or "" for c in row))
PY
```

OCR a scanned PDF (render, then recognize; 200–300 dpi is the useful range):

```bash
pdftoppm -png -r 300 doc.pdf /tmp/scan
for p in /tmp/scan-*.png; do tesseract "$p" - -l eng 2>/dev/null; done
```

## Rules

- **Never pass a PDF to the `read` tool** — it is not an image type there and
  the bytes get treated as text (measured: raw `%PDF-1.4` dump). Render to PNG
  first, or extract text.
- **OCR reads characters, not meaning.** It will not interpret a chart, a
  diagram, or a photograph; only rendering the page and looking at it will.
- Text extraction into a single blob loses column order — if word spacing comes
  out jammed ("Providedproperattribution"), grep for the tokens you need
  instead of reading it linearly, or render the page instead.
- ketch's built-in PDF path has no OCR and wins on speed; use it first for URL
  PDFs and fall back here on empty/garbage output.

## Skeleton

```
pdf-tools/
├── SKILL.md
└── scripts/
    └── verify-env.sh    # binaries + imports + end-to-end smoke test
```

Add task-specific scripts under `scripts/` as the need appears; keep them
non-interactive, write outputs to a temp dir, and print what they produced.
