"""Checks for a sketch-style design page. Read-only.

  python -I -X utf8 check_page.py links <page.html> [extra .md/.html files or folders ...]
      every local href/src exists, every #anchor exists, and relative Markdown links resolve
  python -I -X utf8 check_page.py placeholders <page.html>
      lists template placeholders like [[App]] that are still in the page
  python -I -X utf8 check_page.py numbers <page.html> <expected.json>
      expected.json is {"label": "exact text that must appear"}; reports anything missing
      (workload_model_template.py writes one of these)
  python -I -X utf8 check_page.py privacy <values.txt> <folder> [folder ...]
      values.txt holds one sensitive value per line (phones, e-mails, names). It reports counts and file
      names only, never the values. It also flags any e-mail address. PDFs are read with pdftotext if
      it is installed.

Exit code 1 when something fails.
"""
import html as htmllib
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

TEXT_SUFFIXES = {".html", ".htm", ".md", ".txt", ".json", ".jsonl", ".csv", ".py", ".mjs", ".js", ".sql", ".svg"}


def visible_text(path):
    s = Path(path).read_text(encoding="utf8")
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s, flags=re.S)
    return htmllib.unescape(re.sub(r"<[^>]+>", " ", s))


def cmd_links(page, extras):
    page = Path(page)
    s = page.read_text(encoding="utf8")
    ids = set(re.findall(r'\bid="([^"]+)"', s))
    bad = []
    for ref in re.findall(r'(?:href|src)="([^"]+)"', s):
        if re.match(r"^(https?:|mailto:|data:)", ref):
            continue
        if ref.startswith("#"):
            if ref[1:] and ref[1:] not in ids:
                bad.append((page.name, ref))
            continue
        if not (page.parent / urllib.parse.unquote(ref.split("#")[0].split("?")[0])).exists():
            bad.append((page.name, ref))
    files = []
    for e in extras:
        p = Path(e)
        files += sorted(p.rglob("*.md")) if p.is_dir() else [p]
    for f in files:
        for m in re.finditer(r"\[[^\]]*\]\((<[^>]+>|[^)\s]+)\)", f.read_text(encoding="utf8")):
            t = m.group(1).strip("<>")
            if re.match(r"^(https?:|mailto:|#|/)", t):
                continue
            if not (f.parent / urllib.parse.unquote(t.split("#")[0].split("?")[0])).exists():
                bad.append((str(f), t))
    print(f"broken links: {len(bad)}")
    for b in bad:
        print("  ", b)
    return not bad


def cmd_placeholders(page):
    s = Path(page).read_text(encoding="utf8")
    left = re.findall(r"\[\[[^\]]{0,80}\]\]", s)
    print(f"placeholders left: {len(left)}")
    for p in sorted(set(left))[:50]:
        print("  ", p)
    return not left


def cmd_numbers(page, expected):
    text = re.sub(r"\s+", " ", visible_text(page))
    want = json.loads(Path(expected).read_text(encoding="utf8"))
    missing = {k: v for k, v in want.items() if str(v) not in text}
    print(f"checked {len(want)} numbers; missing: {len(missing)}")
    for k, v in missing.items():
        print(f"  {k}: expected '{v}'")
    return not missing


def cmd_privacy(values_file, folders):
    values = [v.strip() for v in Path(values_file).read_text(encoding="utf8").splitlines() if len(v.strip()) >= 4]
    email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    pdftotext = shutil.which("pdftotext")
    hits = []
    for folder in folders:
        for f in Path(folder).rglob("*"):
            if not f.is_file():
                continue
            if f.suffix.lower() in TEXT_SUFFIXES:
                text = f.read_text(encoding="utf8", errors="replace")
            elif f.suffix.lower() == ".pdf" and pdftotext:
                text = subprocess.run([pdftotext, "-layout", str(f), "-"], capture_output=True, text=True, encoding="utf8", errors="replace").stdout
            else:
                continue
            low = text.lower()
            n = sum(1 for v in values if v.lower() in low)
            e = len(email.findall(text))
            if n or e:
                hits.append((str(f), n, e))
    print(f"reference values: {len(values)}; files with hits: {len(hits)}")
    for f, n, e in hits:
        print(f"  {f}: {n} sensitive value(s), {e} e-mail address(es)")
    return not hits


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    cmd, rest = sys.argv[1], sys.argv[2:]
    ok = {"links": lambda: cmd_links(rest[0], rest[1:]),
          "placeholders": lambda: cmd_placeholders(rest[0]),
          "numbers": lambda: cmd_numbers(rest[0], rest[1]),
          "privacy": lambda: cmd_privacy(rest[0], rest[1:])}[cmd]()
    sys.exit(0 if ok else 1)
