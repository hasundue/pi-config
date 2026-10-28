---
name: pdf-tools
description: >
  Read PDFs on this machine: extract text, render pages to images for visual
  inspection, pull table cells, and OCR scanned documents. Use when a task
  involves a local PDF, when text extracted from a PDF looks empty or mangled,
  or when figures and table layout must actually be seen rather than guessed.
---

# PDF Tools

Confirm the toolchain under Requirements first; if anything is missing, stop there.
Otherwise one script does the work: `scripts/pdf.py`. Start with `info` — it
reports whether the file has a text layer or needs OCR, which decides the rest.

Paths here are relative to this skill's directory — the directory the harness
reports when it loads the skill (the one containing this `SKILL.md`). Never
hardcode an absolute location; resolve against that directory.

```bash
python3 <skill-dir>/scripts/pdf.py info doc.pdf   # pages, text_layer, recommendation
```

Run `<skill-dir>/scripts/pdf.py <subcommand> --help` for flags. Page selections
are 1-based: `--pages 3`, `--pages 1-5`, `--pages 10-`, `--pages 1-3,7`.

## Requirements

PDF work needs all of the following. None of it is optional.

| Kind | Must be available | Used for |
| --- | --- | --- |
| Binary | `pdftoppm`, `pdftotext`, `pdfinfo` | rendering, text extraction, metadata |
| Binary | `tesseract` | OCR |
| Binary | `qpdf` | split, merge, rotate, encrypt/decrypt, overlay, check |
| Python | `pypdf` | page assembly, merge/split, encryption |
| Python | `pdfplumber` | tables and coordinate-filtered text |

Check before starting anything:

```bash
python3 <skill-dir>/scripts/verify-env.py
```

**If anything is missing, stop.** Do not substitute other tools, install
packages, or work around it partially. Report what is missing and which step
needed it, then let the user decide.

## Route by need

| Need | Command |
| --- | --- |
| Is this a scan or a text PDF? | `info` (add `--json` for scripts) |
| Text of the file or a page range | `text --pages 1-5` |
| Two-column paper, correct reading order | `text --columns auto --pages 2-` |
| Unsure of the layout | `pages --pages 1 --dpi 72` then `read` the PNG |
| Words without layout padding | `text --mode raw` |
| See a page: charts, scans, columns | `pages --out /tmp/doc --pages 3` then `read` the PNG |
| Table cells, borderless (papers, reports) | `tables --strategy text --format md` |
| Table cells, ruled (forms) | `tables --format md` (default `lines` strategy) |
| Scanned page to text | `ocr --pages 3 --lang eng` |

`text` and `tables` write to stdout; `pages` writes files and prints their paths.

## Gotchas

- **Never hand a PDF to the `read` tool.** It is not an image type there, so the
  bytes come back as text (measured: a raw `%PDF-1.4` dump). Render first with
  `pages`, or use `text`/`tables`.
- **Two-column layouts interleave.** A plain `text` run reads across both
  columns line by line, mixing them. `info` reports the detected `columns`, and
  `text` warns when the layout looks multi-column; `--columns auto` applies the
  detection, while `--columns 2` forces it. The split happens inside `pdftotext`,
  so word spacing survives. Page 1 usually carries a full-width title and
  abstract, so start at `--pages 2-`.
- **Detection is geometric.** Side-by-side layouts that are not prose — forms,
  two-up slides, checklists — also register as 2 columns, and splitting them is
  sometimes not what you want. Judge from the output: if the text stops making
  sense, retry with `--columns 1`. Never pass `--columns` for a plain
  single-column document, where it discards most of the text.
- **When the layout is unclear, look at it.** Rendered pages are the authority,
  and 72 dpi is enough to see columns, gutters, tables, and where a full-width
  head ends:

  ```bash
  python3 <skill-dir>/scripts/pdf.py pages FILE --out /tmp/look --pages 1 --dpi 72
  ```

  then `read` the PNG. Do this when `info` and the text disagree, when a page is
  a form or slide rather than prose, or when a split cuts a title or swallows a
  paragraph; then pass `--columns N` explicitly.
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
- **Language data.** Only `eng` is available for `ocr`. If another language is
  required, stop and report it instead of OCRing with the wrong model.
- **No usable text layer?** `info` reports `recommendation: ocr`; `text` exits
  with a hint instead of returning a near-empty blob.

## Extending

Add subcommands to `scripts/pdf.py` rather than new scripts: keep stdout
deterministic, write files only when asked, and print what was written. `info`
should stay the entry point that decides text vs OCR.
