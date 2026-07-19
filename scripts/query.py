#!/usr/bin/env python3
"""Sparse-read a built v2 registry plus its adjacent matching index; print exact checksummed load plan/audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contract_validation import CONTRACT_VERSION, ContractError, load_json
from pipeline import query_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path, help="workspace/build/expert-registry.v2.json")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--request", type=Path, help="query-request.v2 JSON")
    group.add_argument("--query", help="query text; creates a local v2 request")
    parser.add_argument("--query-id", default="cli-query")
    parser.add_argument("--risk-domain", action="append", default=[])
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--print-load-plan", action="store_true", help="print exact files/chunks as a human-readable list")
    args = parser.parse_args(argv)
    try:
        if args.request:
            request = load_json(args.request)
        else:
            request = {
                "contract_version": CONTRACT_VERSION,
                "query_id": args.query_id,
                "query": args.query,
                "risk_domains": args.risk_domain,
            }
            if args.top_k is not None:
                request["top_k"] = args.top_k
        output = query_registry(args.registry, request)
    except ContractError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    if args.print_load_plan:
        print("FILES_TO_LOAD")
        for item in output["load_plan"]["file_checksums"]:
            print(f"{item['sha256']} role={item['role']} {item['path']}")
        print("SOURCE_CHUNKS")
        for chunk in output["load_plan"]["source_chunks"]:
            page = f" pages={chunk['page_range']}" if chunk["page_range"] else ""
            print(f"{chunk['sha256']} {chunk['chunk_id']} {chunk['path']} lines={chunk['start_line']}-{chunk['end_line']}{page}")
        print("AUDIT_JSON")
    json.dump(output, sys.stdout, ensure_ascii=False, sort_keys=True, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
