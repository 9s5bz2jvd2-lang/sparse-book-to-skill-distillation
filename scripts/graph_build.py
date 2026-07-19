#!/usr/bin/env python3
"""Build graph-registry.v1.json + vector-index.v1.json from a validated workspace.

Usage:
    python3 scripts/graph_build.py --workspace build/my-book

Requires the v2 lifecycle (intake → distill → validate → build) to have
already completed. Also requires atomic nodes in distilled/atoms/ and
an atom-coverage declaration in distilled/atom-coverage.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contract_validation import ContractError
from atomic_graph import GraphError, build_graph_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path, help="validated workspace root")
    args = parser.parse_args(argv)
    try:
        graph_path = build_graph_registry(args.workspace)
        print(json.dumps({
            "status": "success",
            "graph_registry_path": str(graph_path),
            "vector_index_path": str(graph_path.parent / "vector-index.v1.json"),
        }, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except (ContractError, GraphError) as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
