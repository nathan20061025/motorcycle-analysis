"""Tiny helper: replace/append a marked section in docs/results.md."""
import re
from pathlib import Path


def upsert(path, key, body):
    p = Path(path)
    text = p.read_text(encoding="utf-8") if p.exists() else "# Results\n"
    block = f"<!-- BEGIN {key} -->\n{body.strip()}\n<!-- END {key} -->"
    pat = re.compile(rf"<!-- BEGIN {re.escape(key)} -->.*?<!-- END {re.escape(key)} -->", re.S)
    text = pat.sub(lambda _: block, text) if pat.search(text) else text.rstrip() + "\n\n" + block + "\n"
    p.write_text(text, encoding="utf-8")
