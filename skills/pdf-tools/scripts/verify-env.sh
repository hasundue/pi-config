#!/usr/bin/env bash
# Verify that every PDF tool shipped through
# programs.pi-coding-agent.extraPackages is actually callable.
#
# Checks: binaries on PATH, Python imports, and one end-to-end path
# (generated PDF -> PNG via pdf2image/poppler -> OCR via tesseract).
#
# Usage: verify-env.sh [--no-smoke]
# Exit:  0 = everything works, 1 = something is missing or broken.

set -uo pipefail

run_smoke=1
[[ "${1:-}" == "--no-smoke" ]] && run_smoke=0

fail=0
note() { printf '  %-16s %s\n' "$1" "$2"; }
bad() { note "$1" "MISSING"; fail=1; }

echo "== binaries =="
for bin in pdftoppm pdftotext pdfinfo qpdf tesseract; do
  if path=$(command -v "$bin" 2>/dev/null); then
    note "$bin" "$path"
  else
    bad "$bin"
  fi
done

echo "== python =="
python3 - <<'PY' || fail=1
import importlib
import importlib.metadata
import sys
mods = {
    "pypdf": "pypdf",
    "pdfplumber": "pdfplumber",
    "pdf2image": "pdf2image",
    "pytesseract": "pytesseract",
    "pillow(PIL)": "PIL",
}
bad = 0
for label, mod in mods.items():
    try:
        m = importlib.import_module(mod)
        ver = getattr(m, "__version__", None)
        if not ver:
            try:
                ver = importlib.metadata.version(mod if mod != "PIL" else "pillow")
            except Exception:  # noqa: BLE001
                ver = "?"
        print(f"  {label:<16} {ver}")
    except Exception as exc:  # noqa: BLE001
        print(f"  {label:<16} MISSING ({exc})")
        bad = 1
sys.exit(bad)
PY

if (( run_smoke )); then
  echo "== end-to-end (PDF -> PNG -> OCR) =="
  if ! tmp=$(mktemp -d 2>/dev/null) || [[ -z "$tmp" ]]; then
    note "mktemp" "FAILED — cannot create a temp dir"
    fail=1
    tmp=""
  fi
  if [[ -n "$tmp" ]]; then
    trap 'rm -rf "$tmp"' EXIT
  python3 - "$tmp" <<'PY' || fail=1
import sys
from pathlib import Path
from pypdf import PdfWriter

out = Path(sys.argv[1]) / "blank.pdf"
w = PdfWriter()
w.add_blank_page(width=200, height=100)
with open(out, "wb") as fh:
    w.write(fh)
print(f"  pypdf            wrote {out} ({out.stat().st_size} bytes)")
PY
  if python3 - "$tmp" <<'PY'
import sys
from pathlib import Path
from pdf2image import convert_from_path

pdf = Path(sys.argv[1]) / "blank.pdf"
imgs = convert_from_path(str(pdf), dpi=150)
for i, im in enumerate(imgs, 1):
    p = Path(sys.argv[1]) / f"page-{i}.png"
    im.save(p)
    print(f"  pdf2image        page {i} -> {p.name} {im.size}")
sys.exit(0 if imgs else 1)
PY
  then :; else note "pdf2image" "FAILED (poppler missing?)"; fail=1; fi

  img=""
  for p in "$tmp"/page-*.png; do
    [[ -f "$p" ]] && { img="$p"; break; }
  done
  if [[ -n "$img" ]]; then
    if tesseract "$img" - 2>/dev/null >/dev/null; then
      note "tesseract" "OCR ok on $(basename "$img") (blank page, no text expected)"
    else
      note "tesseract" "FAILED"; fail=1
    fi
  else
    note "tesseract" "SKIPPED (no page image)"; fail=1
  fi
  fi
fi

echo
if (( fail )); then
  echo "RESULT: FAIL — some PDF tooling is not callable."
  echo "Fix: add it to extraPackages in dotnix/configs/home/pi.nix, rebuild, re-login."
  exit 1
fi
echo "RESULT: OK — all PDF tooling is callable."
