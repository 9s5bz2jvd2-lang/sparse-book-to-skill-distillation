#!/usr/bin/env python3
"""Install the reviewed hand-authored semantic artifacts for the synthetic demo only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contract_validation import ContractError
from pipeline import install_curated_artifacts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--curated", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        install_curated_artifacts(args.workspace, args.curated)
    except ContractError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({"status": "reviewed_demo_artifacts_installed", "workspace": args.workspace.as_posix()}, sort_keys=True))
    print("No semantic extraction was automated; these fixture artifacts were authored and reviewed in advance.")
    print("Next required step: python3 scripts/finalize_distillation.py --workspace <workspace>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
