#!/usr/bin/env python3
"""Serial, parallel, and graph/shared-core Skill composition.

Provides versioned contracts and deterministic demonstrations for composing
multiple distilled Skills serially, in parallel, or via shared-core graph
edges.  No network or external dependency.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from contract_validation import CONTRACT_VERSION, ContractError, load_json, validate_instance

GRAPH_CONTRACT_VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"


class CompositionError(ContractError):
    """Composition failure with machine-assertable code."""


def _schema(name: str) -> dict[str, Any]:
    schema = load_json(CONTRACTS / name)
    if not isinstance(schema, dict):
        raise CompositionError("invalid_schema", f"schema root is not an object: {name}")
    return schema


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Serial composition
# ---------------------------------------------------------------------------

def compose_serial(
    manifest: dict[str, Any],
    skill_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compose Skills serially following manifest serial_edges.

    Each edge carries: variables, assumptions, provenance, uncertainty from
    the output of the 'from' Skill as structured input to the 'to' Skill.
    Missing required fields or unresolved references fail closed.
    """
    if manifest.get("contract_version") != GRAPH_CONTRACT_VERSION:
        raise CompositionError("schema_version_mismatch", "manifest contract version mismatch")

    serial_edges = manifest.get("serial_edges", [])
    if not serial_edges:
        raise CompositionError("no_serial_edges", "manifest has no serial composition edges")

    # Detect cycles in serial edges
    edge_graph: dict[str, list[str]] = {}
    for edge in serial_edges:
        edge_graph.setdefault(edge["from_skill"], []).append(edge["to_skill"])
    _detect_serial_cycle(edge_graph)

    chain_trace: list[dict[str, Any]] = []
    current_context: dict[str, Any] = {}

    for edge in serial_edges:
        from_id = edge["from_skill"]
        to_id = edge["to_skill"]

        from_output = skill_outputs.get(from_id)
        if from_output is None:
            raise CompositionError("missing_skill_output", f"Skill '{from_id}' has no output for serial composition")

        # Verify required fields are carried
        carried = edge.get("fields_carried", [])
        missing_fields = [f for f in carried if f not in from_output]
        if missing_fields:
            raise CompositionError("missing_required_fields", f"Skill '{from_id}' output missing fields: {missing_fields}")

        # Build intermediate context
        intermediate = {f: from_output[f] for f in carried if f in from_output}
        intermediate["_source_skill"] = from_id
        intermediate["_target_skill"] = to_id

        # Record provenance and uncertainty propagation
        chain_trace.append({
            "edge": f"{from_id} -> {to_id}",
            "interface_contract": edge["interface_contract"],
            "fields_carried": carried,
            "provenance": from_output.get("provenance", []),
            "uncertainty": from_output.get("uncertainties", []),
            "assumptions": from_output.get("assumptions", []),
        })
        current_context.update(intermediate)

    return {
        "composition_type": "serial",
        "chain_trace": chain_trace,
        "final_context": current_context,
        "edge_count": len(serial_edges),
        "cycle_detected": False,
    }


def _detect_serial_cycle(graph: dict[str, list[str]]) -> None:
    """Detect cycles in serial composition edges."""
    WHITE, GRAY, BLACK = 0, 1, 2
    all_nodes = set(graph.keys())
    for targets in graph.values():
        all_nodes.update(targets)
    color = {n: WHITE for n in all_nodes}

    def dfs(u: str, path: list[str]) -> list[str] | None:
        color[u] = GRAY
        path.append(u)
        for v in graph.get(u, []):
            if color[v] == GRAY:
                idx = path.index(v)
                return path[idx:] + [v]
            if color[v] == WHITE:
                result = dfs(v, path)
                if result:
                    return result
        path.pop()
        color[u] = BLACK
        return None

    for node in sorted(all_nodes):
        if color[node] == WHITE:
            cycle = dfs(node, [])
            if cycle:
                raise CompositionError("serial_cycle", f"cycle detected in serial composition: {cycle}")


# ---------------------------------------------------------------------------
# Parallel composition
# ---------------------------------------------------------------------------

def compose_parallel(
    manifest: dict[str, Any],
    skill_outputs: dict[str, dict[str, Any]],
    problem_input: dict[str, Any],
) -> dict[str, Any]:
    """Compose Skills in parallel, preserving independent outputs and dissent.

    Each parallel group receives the same problem_input. Outputs are joined
    without forced agreement.  Conflicts/unresolved dissent are explicit.
    """
    if manifest.get("contract_version") != GRAPH_CONTRACT_VERSION:
        raise CompositionError("schema_version_mismatch", "manifest contract version mismatch")

    parallel_groups = manifest.get("parallel_groups", [])
    if not parallel_groups:
        raise CompositionError("no_parallel_groups", "manifest has no parallel composition groups")

    group_results: list[dict[str, Any]] = []

    for group in parallel_groups:
        group_id = group["group_id"]
        skill_ids = group["skill_ids"]
        join_policy = group["join_policy"]

        # Verify all skills produced outputs
        group_outputs: dict[str, dict[str, Any]] = {}
        missing = []
        for sid in skill_ids:
            output = skill_outputs.get(sid)
            if output is None:
                missing.append(sid)
            else:
                group_outputs[sid] = output

        if missing:
            raise CompositionError("missing_parallel_output", f"parallel group '{group_id}' missing outputs: {missing}")

        # Collect claims and detect unresolved conflicts
        all_claims: dict[str, list[tuple[str, Any]]] = {}
        for sid, output in group_outputs.items():
            for key, value in output.get("claims", {}).items():
                all_claims.setdefault(key, []).append((sid, value))

        conflicts: list[dict[str, Any]] = []
        for key, entries in all_claims.items():
            values = set(str(v) for _, v in entries)
            if len(values) > 1:
                conflicts.append({
                    "field": key,
                    "positions": {sid: val for sid, val in entries},
                    "resolution": "unresolved" if join_policy["policy_type"] == "preserve_dissent" else "needs_human",
                })

        # Build joined result
        joined = {
            "group_id": group_id,
            "skill_outputs": {sid: output for sid, output in group_outputs.items()},
            "conflicts": conflicts,
            "dissent_preserved": bool(conflicts) and join_policy["policy_type"] == "preserve_dissent",
        }
        group_results.append(joined)

    return {
        "composition_type": "parallel",
        "group_results": group_results,
        "total_groups": len(parallel_groups),
        "total_conflicts": sum(len(g["conflicts"]) for g in group_results),
    }


# ---------------------------------------------------------------------------
# Graph/shared-core composition
# ---------------------------------------------------------------------------

def compose_graph_shared(
    manifest: dict[str, Any],
    skill_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compose via shared-core graph edges without loading all Skills.

    Shared invariants and cross-Skill edges are addressable independently.
    """
    if manifest.get("contract_version") != GRAPH_CONTRACT_VERSION:
        raise CompositionError("schema_version_mismatch", "manifest contract version mismatch")

    shared_edges = manifest.get("graph_shared_edges", [])
    if not shared_edges:
        raise CompositionError("no_shared_edges", "manifest has no graph shared edges")

    edge_results: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    for edge in shared_edges:
        node_id = edge["shared_node_id"]
        referenced_skills = edge["referenced_by_skills"]
        invariant = edge["invariant"]

        # Verify all referenced skills produced outputs
        present = [s for s in referenced_skills if s in skill_outputs]
        absent = [s for s in referenced_skills if s not in skill_outputs]

        # Check invariant satisfaction
        invariant_satisfied = True
        if present:
            # Verify the invariant holds across present skills
            # (deterministic check: all present skills must reference the node)
            for skill_id in present:
                output = skill_outputs[skill_id]
                referenced_nodes = output.get("referenced_shared_nodes", [])
                if node_id not in referenced_nodes:
                    invariant_satisfied = False
                    violations.append({
                        "shared_node_id": node_id,
                        "skill_id": skill_id,
                        "violation": f"Skill does not reference shared node {node_id}",
                    })

        edge_results.append({
            "shared_node_id": node_id,
            "referenced_skills": referenced_skills,
            "present_skills": present,
            "absent_skills": absent,
            "invariant": invariant,
            "invariant_satisfied": invariant_satisfied,
        })

    return {
        "composition_type": "graph_shared",
        "edge_results": edge_results,
        "violations": violations,
        "all_invariants_satisfied": len(violations) == 0,
    }


# ---------------------------------------------------------------------------
# Micro-model manifest
# ---------------------------------------------------------------------------

def build_composition_manifest(
    workspace: Path,
    graph_registry_path: Path,
    serial_edges: list[dict[str, Any]] | None = None,
    parallel_groups: list[dict[str, Any]] | None = None,
    shared_edges: list[dict[str, Any]] | None = None,
) -> Path:
    """Build a composition-manifest.v1.json for the workspace."""
    workspace = workspace.resolve()
    graph_registry_path = graph_registry_path.resolve()

    graph = load_json(graph_registry_path)
    base_registry_path = workspace / "build" / "expert-registry.v2.json"
    base_registry = load_json(base_registry_path)
    shared_core_path = workspace / "distilled" / "shared-core.md"
    shared_core_sha = _sha256_bytes(shared_core_path.read_bytes())

    # Build evaluation fixtures list
    fixture_dir = workspace / "tests" / "fixtures"
    eval_fixtures: list[dict[str, str]] = []
    if fixture_dir.is_dir():
        for path in sorted(fixture_dir.glob("*.json")):
            eval_fixtures.append({
                "fixture_id": path.stem,
                "path": str(path.relative_to(workspace)),
            })

    manifest = {
        "contract_version": GRAPH_CONTRACT_VERSION,
        "manifest_id": f"composition-{_sha256_bytes(graph['graph_id'].encode())[:16]}",
        "manifest_version": "1.0.0",
        "member_skills": [{
            "skill_id": "sparse-book-distillation",
            "role": "primary",
            "graph_registry_path": str(graph_registry_path.relative_to(workspace)),
            "input_schema": "query-request.v2",
            "output_schema": "atomic-route-output.v1",
        }],
        "shared_core": {
            "path": str(shared_core_path.relative_to(workspace)),
            "sha256": shared_core_sha,
        },
        "router_policy": {
            "policy_type": "two_stage_sparse_graph",
            "stages": [
                {"stage_id": "coarse_domain", "description": "Expert/domain-level filtering by trigger terms"},
                {"stage_id": "atomic_selection", "description": "Fine-grained atomic node scoring and selection"},
            ],
        },
        "serial_edges": serial_edges or [],
        "parallel_groups": parallel_groups or [],
        "graph_shared_edges": shared_edges or [],
        "required_schemas": [
            "atomic-node.v1.schema.json",
            "graph-registry.v1.schema.json",
            "atomic-route-output.v1.schema.json",
            "composition-manifest.v1.schema.json",
        ],
        "safety_policy": {
            "must_expand_safety_nodes": graph.get("safety_sweep_config", {}).get("always_expand_safety_nodes", []),
            "fail_closed_on_missing": True,
        },
        "evaluation_fixtures": eval_fixtures,
        "version_hashes": {
            "graph_registry": _sha256_bytes(graph_registry_path.read_bytes()),
            "base_registry": _sha256_bytes(base_registry_path.read_bytes()),
        },
    }
    validate_instance(manifest, _schema("composition-manifest.v1.schema.json"))

    manifest_path = workspace / "build" / "composition-manifest.v1.json"
    _canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    manifest_path.write_text(_canonical, encoding="utf-8")
    return manifest_path
