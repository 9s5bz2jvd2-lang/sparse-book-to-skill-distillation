#!/usr/bin/env python3
"""Check repository-local paths referenced by Markdown documentation."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_DIRS = [
    ROOT,
    ROOT / "assets",
    ROOT / "docs",
    ROOT / "reference",
    ROOT / "reference" / "experts",
    ROOT / "examples" / "from-zero",
    ROOT / "examples" / "from-zero" / "source",
    ROOT / "examples" / "from-zero" / "curated",
    ROOT / "examples" / "from-zero" / "curated" / "l3",
]
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
CODE_PATH_RE = re.compile(r"`((?:contracts|reference|scripts|assets|docs|examples|tests)/[A-Za-z0-9_.\-/]+)`")


def markdown_files() -> list[Path]:
    files: list[Path] = []
    for directory in DOC_DIRS:
        if directory.is_dir():
            files.extend(directory.glob("*.md"))
    return sorted(set(files))


def main() -> int:
    failures: list[str] = []
    for document in markdown_files():
        text = document.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            target = target.split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            candidate = (document.parent / target).resolve()
            try:
                candidate.relative_to(ROOT.resolve())
            except ValueError:
                failures.append(f"{document.relative_to(ROOT)}: link escapes repository: {target}")
                continue
            if not candidate.exists():
                failures.append(f"{document.relative_to(ROOT)}: missing link target: {target}")
        for target in CODE_PATH_RE.findall(text):
            candidate = ROOT / target
            if not candidate.exists():
                failures.append(f"{document.relative_to(ROOT)}: missing code path: {target}")
    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1
    print(f"PASS documentation paths: {len(markdown_files())} Markdown files checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
