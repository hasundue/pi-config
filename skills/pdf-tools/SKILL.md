---
name: pdf-tools
description: >
  Read PDFs on this machine: extract text, render pages to images for visual
  inspection, pull table cells, and OCR scanned documents. Use when a task
  involves a local PDF, when text extracted from a PDF looks empty or mangled,
  or when figures and table layout must actually be seen rather than guessed.
---

# PDF Tools

One script does the work: `scripts/pdf.py`. Start with `info` — it reports whether
the file has a text layer or needs OCR, which decides everything else.

```bash
P=~/.pi/agent/skills/pdf-tools/scripts/pdf.py
python3 "$P" info doc.pdf     # pages, metadata, text_layer, recommendation
```

Run `python3 "$P" <subcommand> --help` for flags. Page selections are 1-based:
`--pages 3`, `--pages 1-5`, `--pages 10-`, `--pages 1-3,7`.

## Route by need

| Need | Command |
| --- | --- |
| Is this a scan or a text PDF? | `info` (add `--json` for scripts) |
| Text of the file or a page range | `text --pages 1-5` |
| Words without layout padding | `text --mode raw` |
| See a page: charts, scans, columns | `pages --out /tmp/doc --pages 3` then `read` the PNG |
| Table cells, borderless (papers, reports) | `tables --strategy text --format md` |
| Table cells, ruled (forms) | `tables --format md` (default `lines` strategy) |
| Scanned page to text | `ocr --pages 3 --lang eng` |
| Toolchain health check | `python3 scripts/verify-env.py` |

`text` and `tables` write to stdout; `pages` writes files and prints their paths.

## Gotchas

- **Never hand a PDF to the `read` tool.** It is not an image type there, so the
  bytes come back as text (measured: a raw `%PDF-1.4` dump). Render first with
  `pages`, or use `text`/`tables`.
- **ketch vs local extraction.** For a PDF behind a URL, `ketch scrape <url>` is
  the cheapest first look (no OCR), but its extractor drops inter-word spacing —
  text comes out jammed. When the wording matters, download the file and use
  `pdf.py text`, which keeps spacing via `pdftotext -layout`.
- **`lines` vs `text` table strategy.** `lines` needs drawn rules and returns
  nothing on academic papers; `text` infers columns from whitespace, works on
  papers and reports, but collapses spaces inside cells.
- **OCR reads characters, not meaning.** A chart, diagram, or photograph is not
  interpreted by `ocr`; render with `pages` and look at it.
- **Cost of rendering.** Every page image is a separate attachment. Select pages
  and use `--dpi 150` for reading; reserve `--dpi 300` for OCR.
- **Language data.** `ocr --lang eng` is all that ships here. Other languages
  need the matching tesseract data added to `extraPackages`.
- **No usable text layer?** `info` reports `recommendation: ocr`; `text` exits
  with a hint instead of returning a near-empty blob.

## Environment

Installed through `programs.pi-coding-agent.extraPackages` in
`dotnix/configs/home/pi.nix`, so it is on `PATH` for this agent and its `bash`
tool — nothing to install at runtime. After changing that file, rebuild
(`nix run .#home-build`), switch (`nix run .#home-switch`), and restart pi.

| Kind | Package | Gives you |
| --- | --- | --- |
| CLI | `poppler-utils` | `pdftoppm`, `pdftotext`, `pdfinfo`, `pdfimages`, `pdfunite`, `pdfseparate`, `pdftohtml` |
| CLI | `tesseract` | OCR, with `tsv` / `hocr` output for word coordinates |
| CLI | `qpdf` | split, merge, rotate, encrypt/decrypt, overlay, structural check |
| Python | `pypdf` | pure Python page assembly, merge/split, encryption |
| Python | `pdfplumber` | pure Python tables and coordinate-filtered text |

`pdf2image` and `pytesseract` are deliberately absent: both merely shell out to
the binaries above. There is no `pymupdf`, so rendering always goes through
`pdftoppm`.

## Extending

Add subcommands to `scripts/pdf.py` rather than new scripts: keep stdout
deterministic, write files only when asked, and print what was written. `info`
should stay the entry point that decides text vs OCR.
