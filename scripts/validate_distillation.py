#!/usr/bin/env python3
"""Fail unless every source chunk is processed, mapped, cited with valid lines, and backed by L3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contract_validation import ContractError
from pipeline import validate_distillation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = validate_distillation(args.workspace)
    except ContractError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({
        "status": "distillation_complete",
        "full_text_status": result["manifest"]["full_text_status"],
        "sources": len(result["manifest"]["sources"]),
        "chunks": len(result["manifest"]["chunks"]),
        "knowledge_nodes": result["node_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
