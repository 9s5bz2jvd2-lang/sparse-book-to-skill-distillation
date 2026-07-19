#!/usr/bin/env python3
"""Build the canonical expert registry/index from validated per-chunk semantic artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contract_validation import ContractError
from pipeline import build_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        _, _, registry = build_registry(args.workspace)
    except ContractError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({
        "status": "registry_built",
        "build_id": registry["build_id"],
        "experts": len(registry["experts"]),
        "registry": (args.workspace / "build" / "expert-registry.v2.json").as_posix(),
        "index": (args.workspace / "build" / "expert-index.v2.json").as_posix(),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
