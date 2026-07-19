#!/usr/bin/env python3
"""Claim/resume or checkpoint ordered semantic-review batches without skipping chunks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contract_validation import ContractError
from pipeline import checkpoint_review_batch, claim_review_batch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    next_parser = subparsers.add_parser("next", help="return active batch or claim the next contiguous batch")
    next_parser.add_argument("--workspace", required=True, type=Path)
    next_parser.add_argument("--batch-size", type=int, default=3)
    checkpoint_parser = subparsers.add_parser("checkpoint", help="commit the longest valid authored contiguous prefix of the active batch")
    checkpoint_parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "checkpoint":
            result = checkpoint_review_batch(args.workspace)
        else:
            result = claim_review_batch(args.workspace, batch_size=args.batch_size)
    except ContractError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
