#!/usr/bin/env python3
"""Query a built graph registry with vector-aware sparse routing.

Usage:
    python3 scripts/graph_query.py \\
      --graph-registry build/my-book/build/graph-registry.v1.json \\
      --query "your task" \\
      --query-id local-001 \\
      --pretty \\
      --print-load-plan

Supports optional --query-vectors-json for multi-channel vector queries
and --residual-bank for versioned residual revisit.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from artifact_io import write_json_atomic
from contract_validation import ContractError, load_json
from atomic_graph import GraphError, route_graph


def _write_json_atomic(path: Path, value: object) -> None:
    """Write one JSON artifact atomically; never expose a partially written bank/route."""
    target = path.expanduser().resolve()
    try:
        write_json_atomic(path, value)
    except (OSError, TypeError, ValueError) as exc:
        raise GraphError("output_write_failed", f"cannot persist JSON artifact {target}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-registry", required=True, type=Path, help="graph-registry.v1.json")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--request", type=Path, help="query-request JSON")
    group.add_argument("--query", help="query text")
    parser.add_argument("--query-id", default="cli-query")
    parser.add_argument("--risk-domain", action="append", default=[])
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--vector-top-k", type=int)
    parser.add_argument("--query-vectors-json", type=Path, help="JSON file with query_vectors dict")
    parser.add_argument("--residual-bank", type=Path, help="prior residual-bank.v1 JSON file")
    parser.add_argument("--output", type=Path, help="atomically persist the complete route output JSON")
    parser.add_argument("--residual-output", type=Path, help="atomically persist the next residual bank; may equal --residual-bank")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--print-load-plan", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.request:
            request = load_json(args.request)
        else:
            request = {
                "query_id": args.query_id,
                "query": args.query,
                "risk_domains": args.risk_domain,
            }
            if args.top_k is not None:
                request["top_k"] = args.top_k
            if args.vector_top_k is not None:
                request["vector_top_k"] = args.vector_top_k

        residual_bank = None
        if args.residual_bank:
            residual_bank = load_json(args.residual_bank)

        if args.query_vectors_json:
            request["query_vectors"] = load_json(args.query_vectors_json)

        graph_input = args.graph_registry.expanduser().resolve()
        immutable_inputs = {graph_input}
        for input_path in (args.request, args.query_vectors_json):
            if input_path is not None:
                immutable_inputs.add(input_path.expanduser().resolve())
        output_path = args.output.expanduser().resolve() if args.output else None
        residual_output_path = args.residual_output.expanduser().resolve() if args.residual_output else None
        residual_input_path = args.residual_bank.expanduser().resolve() if args.residual_bank else None
        if output_path and residual_output_path and output_path == residual_output_path:
            raise GraphError("output_path_collision", "--output and --residual-output must be different files")
        if output_path and (output_path in immutable_inputs or output_path == residual_input_path):
            raise GraphError("output_path_collision", "--output must not overwrite an input artifact")
        if residual_output_path and residual_output_path in immutable_inputs:
            raise GraphError("output_path_collision", "--residual-output must not overwrite graph/request/vector input")
        output = route_graph(args.graph_registry, request, residual_bank)
        if args.output:
            _write_json_atomic(args.output, output)
        if args.residual_output:
            _write_json_atomic(args.residual_output, output["residual"])
    except (ContractError, GraphError) as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2

    if args.print_load_plan:
        lp = output["load_plan"]
        print(f"STATUS: {output['status']}")
        print(f"NODES: {lp['node_count']} CHUNKS: {lp['chunk_count']} FILES: {lp['file_count']}")
        print("FILES_TO_LOAD")
        for item in lp["file_checksums"]:
            print(f"{item['sha256']} role={item['role']} {item['path']}")
        print("SOURCE_CHUNKS")
        for chunk in lp["source_chunks"]:
            print(f"{chunk['sha256']} {chunk['chunk_id']} {chunk['path']} lines={chunk['start_line']}-{chunk['end_line']}")
        print("CLOSURE")
        cl = output["closure"]
        print(f"  expanded: {len(cl['expanded_node_ids'])} budget: {cl['budget']} truncated: {cl['closure_truncated']}")
        print("SAFETY")
        sf = output["safety"]
        print(f"  baseline: {sf['baseline_checks_run']} global_invariant: {sf['global_invariant_included']} risk_domain: {sf['risk_domain_included']}")
        print("AUDIT_JSON")

    json.dump(output, sys.stdout, ensure_ascii=False, sort_keys=True, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
