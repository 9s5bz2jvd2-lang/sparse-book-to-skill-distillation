#!/usr/bin/env python3
"""Generate one pending semantic artifact template for every ingested source chunk."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contract_validation import ContractError
from pipeline import prepare_distillation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = prepare_distillation(args.workspace)
    except ContractError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({"status": "templates_ready", **result}, sort_keys=True))
    print("Semantic step required: use review_queue.py for durable contiguous batches; an agent/human must read every complete chunk, author every artifact, and complete semantic-review.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
