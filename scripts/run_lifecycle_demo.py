#!/usr/bin/env python3
"""Run source -> chunks -> semantic artifacts -> registry -> sparse query from an empty workspace."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from contract_validation import ContractError, load_json
from atomic_graph import GraphError, build_graph_registry, route_graph
from pipeline import ROOT, build_registry, finalize_queue_and_source_map, install_curated_artifacts, intake_sources, prepare_distillation, query_registry, validate_distillation

SOURCE = ROOT / "examples" / "from-zero" / "source"
CURATED = ROOT / "examples" / "from-zero" / "curated"
REQUEST = ROOT / "examples" / "from-zero" / "request.json"
DEFAULT_WORKSPACE = ROOT / "build" / "from-zero-demo"


def safe_clean(workspace: Path) -> None:
    resolved = workspace.resolve()
    build_root = (ROOT / "build").resolve()
    try:
        relative = resolved.relative_to(build_root)
    except ValueError as exc:
        raise RuntimeError("demo cleanup is restricted to a child of the repository build directory") from exc
    if not relative.parts:
        raise RuntimeError("demo workspace must be a strict child of the repository build directory")
    if resolved.exists():
        shutil.rmtree(resolved)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--keep-workspace", action="store_true")
    args = parser.parse_args(argv)
    workspace = args.workspace
    cleanup_safe = False
    try:
        safe_clean(workspace)
        cleanup_safe = True
        manifest = intake_sources(SOURCE, workspace, max_lines_per_chunk=6)
        prepared = prepare_distillation(workspace)
        install_curated_artifacts(workspace, CURATED)
        finalize_queue_and_source_map(workspace)
        validated = validate_distillation(workspace)
        build_registry(workspace)
        registry_for_query = workspace / "build" / "expert-registry.v2.json"
        output = query_registry(registry_for_query, load_json(REQUEST))
        graph_path = build_graph_registry(workspace)
        graph_request = load_json(REQUEST)
        graph_request["query_id"] = "from-zero-demo-graph-query"
        graph_output = route_graph(graph_path, graph_request)
        trace = {
            "contract_version": "2.0.0",
            "stages": [
                {"stage": "source_intake", "full_text_status": manifest["full_text_status"], "sources": len(manifest["sources"]), "chunks": len(manifest["chunks"])},
                {"stage": "work_queue_and_templates", "items": prepared["chunks"], "initial_status": "pending"},
                {"stage": "semantic_artifact_install", "semantic_step": "reviewed_hand_authored_fixture_artifacts_not_automated_inference"},
                {"stage": "queue_and_source_map_finalize", "status_source": "agent_authored_records"},
                {"stage": "completeness_validation", "knowledge_nodes": validated["node_count"]},
                {"stage": "registry_build", "registry": (workspace / "build" / "expert-registry.v2.json").as_posix(), "index": (workspace / "build" / "expert-index.v2.json").as_posix()},
                {"stage": "sparse_query", "status": output["status"], "selected_experts": output["selected_experts"], "safety_sweep_activated": output["safety_sweep"]["activated"]},
                {"stage": "atomic_graph_build", "graph_registry": graph_path.as_posix(), "vector_index": (workspace / "build" / "vector-index.v1.json").as_posix()},
                {"stage": "atomic_graph_query", "status": graph_output["status"], "selected_nodes": [row["node_id"] for row in graph_output["selected_nodes"]], "closure_budget": graph_output["closure"]["budget"], "residual_bank_version": graph_output["residual"]["bank_version"]},
            ],
            "query_output": output,
            "graph_query_output": graph_output,
        }
        print(json.dumps(trace, ensure_ascii=False, sort_keys=True, indent=2))
    except (ContractError, GraphError, RuntimeError) as exc:
        if isinstance(exc, ContractError):
            print(json.dumps(exc.as_dict(), ensure_ascii=False, sort_keys=True), file=sys.stderr)
        else:
            print(f"demo_error: {exc}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_workspace and cleanup_safe:
            safe_clean(workspace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
