#!/usr/bin/env python3
"""Ingest UTF-8 txt/md (or explicitly authorized pdftotext PDF) into a full chunk workspace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contract_validation import ContractError
from pipeline import intake_sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="UTF-8 .txt/.md file or directory; .pdf needs opt-in adapter")
    parser.add_argument("--workspace", required=True, type=Path, help="new or empty explicit local output directory")
    parser.add_argument("--chunk-lines", type=int, default=80, help="deterministic maximum physical lines per chunk (1-1000)")
    parser.add_argument("--allow-pdftotext", action="store_true", help="authorize reviewed local pdftotext subprocess for PDF input")
    args = parser.parse_args(argv)
    try:
        manifest = intake_sources(
            args.source,
            args.workspace,
            max_lines_per_chunk=args.chunk_lines,
            allow_pdftotext=args.allow_pdftotext,
        )
    except ContractError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({
        "status": "intake_complete",
        "manifest_id": manifest["manifest_id"],
        "full_text_status": manifest["full_text_status"],
        "sources": len(manifest["sources"]),
        "chunks": len(manifest["chunks"]),
        "workspace": args.workspace.as_posix(),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
