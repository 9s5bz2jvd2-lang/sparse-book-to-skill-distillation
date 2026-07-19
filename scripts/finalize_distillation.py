#!/usr/bin/env python3
"""Finalize queue/source-map from completed agent-authored records, then run full validation separately."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contract_validation import ContractError
from pipeline import finalize_queue_and_source_map


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        finalize_queue_and_source_map(args.workspace)
    except ContractError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({"status": "queue_and_source_map_finalized", "workspace": args.workspace.as_posix()}, sort_keys=True))
    print("Next required gate: python3 scripts/validate_distillation.py --workspace <workspace>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
