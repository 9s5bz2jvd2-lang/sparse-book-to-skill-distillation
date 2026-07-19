#!/usr/bin/env python3
"""K3-inspired graph-sparse atomic routing module.

Extends the existing v2 lifecycle with extremely fine-grained atomic knowledge
nodes, multi-stage sparse gating, vector-first candidate union, dependency/
provenance/safety closure, versioned residual bank, and scoped safety.
Uses only standard-library deterministic logic.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from artifact_io import write_json_atomic
from contract_validation import CONTRACT_VERSION, ContractError, load_json, validate_instance
from vector_sim import (
    VectorError,
    cosine_similarity,
    get_backend,
    resolve_backend,
    score_vector_candidates,
    symbolic_rerank,
    validate_channel_config,
    validate_node_vectors,
)

GRAPH_CONTRACT_VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"


class GraphError(ContractError):
    """Graph-sparse extension failure with machine-assertable code."""


def _schema(name: str) -> dict[str, Any]:
    schema = load_json(CONTRACTS / name)
    if not isinstance(schema, dict):
        raise GraphError("invalid_schema", f"schema root is not an object: {name}")
    return schema


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    """Persist one graph artifact without fixed-name temp collisions."""
    write_json_atomic(path, value)


# ---------------------------------------------------------------------------
# A. Atomic node loading and validation
# ---------------------------------------------------------------------------

def load_atomic_nodes(workspace: Path) -> list[dict[str, Any]]:
    """Load all atomic-node.v1 JSON files from workspace/distilled/atoms/."""
    atoms_dir = workspace / "distilled" / "atoms"
    if atoms_dir.is_symlink() or not atoms_dir.is_dir():
        raise GraphError("unsafe_atoms_dir" if atoms_dir.is_symlink() else "missing_atoms_dir", "distilled/atoms/ must be a regular directory")
    schema = _schema("atomic-node.v1.schema.json")
    nodes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for path in sorted(atoms_dir.glob("*.json")):
        if path.is_symlink():
            raise GraphError("unsafe_atom_file", f"atomic node is a symlink: {path.name}")
        node = load_json(path)
        validate_instance(node, schema)
        if node["contract_version"] != GRAPH_CONTRACT_VERSION:
            raise GraphError("schema_version_mismatch", f"atomic node contract version mismatch: {node['node_id']}")
        if node["node_id"] in seen_ids:
            raise GraphError("duplicate_node_id", f"duplicate atomic node_id: {node['node_id']}")
        seen_ids.add(node["node_id"])
        nodes.append(node)
    if not nodes:
        raise GraphError("no_atomic_nodes", "no atomic nodes found in distilled/atoms/")
    return nodes


def _validate_source_refs(nodes: list[dict[str, Any]], chunks: dict[str, dict[str, Any]]) -> None:
    """Every chunk-type source_ref must point to a known chunk with valid line range."""
    for node in nodes:
        ref = node["source_ref"]
        if ref["ref_type"] == "chunk":
            chunk_id = ref.get("chunk_id")
            if chunk_id not in chunks:
                raise GraphError("broken_provenance", f"atomic node {node['node_id']} references unknown chunk: {chunk_id}")
            chunk = chunks[chunk_id]
            if ref.get("source_id") != chunk["source_id"]:
                raise GraphError("broken_provenance", f"atomic node {node['node_id']} source_id mismatch for chunk {chunk_id}")
            if not (chunk["start_line"] <= ref["start_line"] <= ref["end_line"] <= chunk["end_line"]):
                raise GraphError("broken_provenance", f"atomic node {node['node_id']} line range escapes chunk {chunk_id}")


def _validate_dependencies(nodes: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Validate all dependency targets exist; return adjacency for cycle detection."""
    node_ids = {n["node_id"] for n in nodes}
    adj: dict[str, set[str]] = {nid: set() for nid in node_ids}
    for node in nodes:
        for dep in node["dependencies"]:
            target = dep["target_node_id"]
            if target not in node_ids:
                raise GraphError("broken_dependency", f"atomic node {node['node_id']} depends on unknown node: {target}")
            if target == node["node_id"]:
                raise GraphError("self_dependency", f"atomic node {node['node_id']} depends on itself")
            adj[node["node_id"]].add(target)
        for rel in node["relations"]:
            target = rel["target_node_id"]
            if target not in node_ids:
                raise GraphError("broken_relation", f"atomic node {node['node_id']} relates to unknown node: {target}")
            if target == node["node_id"]:
                raise GraphError("self_relation", f"atomic node {node['node_id']} relates to itself")
            if rel["relation_type"] in {"safety_requires", "provenance_chain"}:
                adj[node["node_id"]].add(target)
    return adj


def _detect_cycle(adj: dict[str, set[str]]) -> list[str] | None:
    """Detect a cycle using DFS; return the cycle path or None."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in adj}
    parent = {n: None for n in adj}

    def dfs(u: str, path: list[str]) -> list[str] | None:
        color[u] = GRAY
        path.append(u)
        for v in sorted(adj.get(u, set())):
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

    for node in sorted(adj):
        if color[node] == WHITE:
            cycle = dfs(node, [])
            if cycle:
                return cycle
    return None


# ---------------------------------------------------------------------------
# B. Atom coverage validation
# ---------------------------------------------------------------------------

def validate_atom_coverage(workspace: Path) -> dict[str, Any]:
    """Bind every validated v2 record to an exact atomic coverage decision."""
    coverage_path = workspace / "distilled" / "atom-coverage.json"
    if not coverage_path.is_file():
        raise GraphError("missing_atom_coverage", "distilled/atom-coverage.json not found")

    coverage = load_json(coverage_path)
    validate_instance(coverage, _schema("atom-coverage.v1.schema.json"))
    manifest_path = workspace / "source-manifest.json"
    source_map_path = workspace / "distilled" / "source-map.json"
    manifest = load_json(manifest_path)
    source_map = load_json(source_map_path)

    manifest_sha = _sha256_bytes(manifest_path.read_bytes())
    if coverage["source_manifest_sha256"] != manifest_sha:
        raise GraphError("coverage_manifest_mismatch", "atom-coverage source_manifest_sha256 does not match")
    if source_map.get("source_manifest_sha256") != manifest_sha:
        raise GraphError("source_map_manifest_mismatch", "source-map source_manifest_sha256 does not match")

    chunk_ids = {chunk["chunk_id"] for chunk in manifest["chunks"]}
    coverage_by_chunk = {entry["chunk_id"]: entry for entry in coverage["entries"]}
    source_by_chunk = {entry["chunk_id"]: entry for entry in source_map["entries"]}
    if len(coverage_by_chunk) != len(coverage["entries"]):
        raise GraphError("coverage_duplicate_chunk", "atom-coverage contains duplicate chunk_id entries")
    if len(source_by_chunk) != len(source_map["entries"]):
        raise GraphError("source_map_duplicate_chunk", "source-map contains duplicate chunk_id entries")
    if set(coverage_by_chunk) != chunk_ids:
        raise GraphError(
            "coverage_gap",
            f"atom-coverage entries don't match manifest chunks: missing={sorted(chunk_ids-set(coverage_by_chunk))} extra={sorted(set(coverage_by_chunk)-chunk_ids)}",
        )
    if set(source_by_chunk) != chunk_ids:
        raise GraphError("source_map_gap", "source-map entries do not exactly match manifest chunks")

    nodes = load_atomic_nodes(workspace)
    nodes_by_id = {node["node_id"]: node for node in nodes}
    chunk_atom_ids: dict[str, set[str]] = {chunk_id: set() for chunk_id in chunk_ids}
    for node in nodes:
        ref = node["source_ref"]
        if ref["ref_type"] == "chunk":
            chunk_atom_ids.setdefault(ref["chunk_id"], set()).add(node["node_id"])

    declared_atom_ids: set[str] = set()
    for chunk_id in sorted(chunk_ids):
        decision = coverage_by_chunk[chunk_id]
        source_entry = source_by_chunk[chunk_id]
        artifact_path = workspace_path(workspace, source_entry["artifact_path"])
        if not artifact_path.is_file():
            raise GraphError("coverage_missing_artifact", f"coverage record missing for chunk {chunk_id}")
        record = load_json(artifact_path)
        processing_status = record.get("processing_status")
        if processing_status != source_entry["processing_status"]:
            raise GraphError("coverage_status_mismatch", f"chunk {chunk_id}: source-map and record status differ")

        atom_ids = decision["atom_ids"]
        if len(atom_ids) != len(set(atom_ids)):
            raise GraphError("coverage_duplicate_atom", f"chunk {chunk_id}: duplicate atom_ids")
        overlap = declared_atom_ids & set(atom_ids)
        if overlap:
            raise GraphError("coverage_duplicate_atom", f"atom IDs declared for multiple chunks: {sorted(overlap)}")
        declared_atom_ids.update(atom_ids)

        if processing_status == "complete":
            if not record.get("knowledge_nodes"):
                raise GraphError("coverage_record_invalid", f"chunk {chunk_id}: complete record has no knowledge_nodes")
            if decision["status"] != "atoms_authored" or not atom_ids:
                raise GraphError("coverage_incomplete", f"chunk {chunk_id}: reusable record requires non-empty atoms_authored")
            chunk_bound = set()
            for atom_id in atom_ids:
                node = nodes_by_id.get(atom_id)
                if node is None:
                    raise GraphError("coverage_atom_binding_mismatch", f"chunk {chunk_id}: unknown atom binding {atom_id}")
                ref = node["source_ref"]
                if ref["ref_type"] == "chunk":
                    if ref.get("chunk_id") != chunk_id:
                        raise GraphError("coverage_atom_binding_mismatch", f"chunk {chunk_id}: atom {atom_id} is bound to another chunk")
                    chunk_bound.add(atom_id)
                elif node["validation_state"] == "validated":
                    raise GraphError("coverage_fixture_laundering", f"chunk {chunk_id}: synthetic fixture atom {atom_id} cannot be labeled validated")
            if not chunk_bound:
                raise GraphError("coverage_missing_chunk_atom", f"chunk {chunk_id}: reusable record requires at least one chunk-sourced atom")
            if chunk_bound != chunk_atom_ids.get(chunk_id, set()):
                raise GraphError("coverage_atom_binding_mismatch", f"chunk {chunk_id}: declared chunk-bound atoms do not match actual chunk-sourced atoms")
        elif processing_status == "complete_no_reusable_knowledge":
            if decision["status"] != "no_atomizable_content" or atom_ids or not decision.get("reason", "").strip():
                raise GraphError("coverage_status_mismatch", f"chunk {chunk_id}: no-reusable record requires empty no_atomizable_content decision with reason")
            if chunk_atom_ids.get(chunk_id):
                raise GraphError("coverage_atom_binding_mismatch", f"chunk {chunk_id}: no-reusable record has chunk-sourced atoms")
        else:
            raise GraphError("coverage_incomplete", f"chunk {chunk_id}: unsupported or pending processing_status {processing_status!r}")

    if declared_atom_ids != set(nodes_by_id):
        raise GraphError("coverage_atom_binding_mismatch", "coverage decisions do not exactly account for every atomic node")
    return coverage


# ---------------------------------------------------------------------------
# B. Multi-stage sparse gating
# ---------------------------------------------------------------------------

def _extract_intent_tokens(query: str) -> list[str]:
    """Extract normalized intent tokens from query (deterministic lexical)."""
    normalized = _normalize(query)
    tokens = [t for t in re.split(r"[^\w]+", normalized) if len(t) > 1]
    return sorted(set(tokens))


def _stage1_domain_route(
    nodes: list[dict[str, Any]],
    intent_tokens: list[str],
    explicit_risk_domains: list[str],
) -> tuple[dict[str, float], list[str]]:
    """Stage 1: coarse domain/module routing based on expert_id clustering."""
    domain_experts: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        domain_experts.setdefault(node["expert_id"], []).append(node)

    domain_scores: dict[str, float] = {}
    for expert_id, expert_nodes in domain_experts.items():
        score = 0.0
        for node in expert_nodes:
            for term in node["triggers"]:
                if _normalize(term["term"]) in " ".join(intent_tokens):
                    score += term["weight"]
            for anti in node["anti_triggers"]:
                if _normalize(anti) in " ".join(intent_tokens):
                    score -= 100
        domain_scores[expert_id] = score

    selected = []
    for domain in sorted(domain_scores):
        if domain_scores[domain] > 0:
            selected.append(domain)
    if explicit_risk_domains:
        for domain in sorted(domain_experts):
            node_kinds = {n["node_kind"] for n in domain_experts[domain]}
            if "red_line" in node_kinds and domain not in selected:
                selected.append(domain)
    return domain_scores, sorted(selected)


def _stage2_atomic_route(
    nodes: list[dict[str, Any]],
    selected_domains: list[str],
    intent_tokens: list[str],
    minimum_score: int = 2,
    top_k: int = 5,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Stage 2: fine-grained atomic node selection within selected domains."""
    candidates = [n for n in nodes if n["expert_id"] in selected_domains]
    query_text = " ".join(intent_tokens)

    node_scores: list[dict[str, Any]] = []
    for node in candidates:
        positive_hits = [t["term"] for t in node["triggers"] if _normalize(t["term"]) in query_text]
        score = sum(t["weight"] for t in node["triggers"] if t["term"] in set(positive_hits))
        anti_hits = [a for a in node["anti_triggers"] if _normalize(a) in query_text]
        eligible = score >= minimum_score and not anti_hits
        node_scores.append({
            "node_id": node["node_id"],
            "score": score,
            "hits": positive_hits,
            "anti_hits": anti_hits,
            "eligible": eligible,
            "node_kind": node["node_kind"],
        })

    node_scores.sort(key=lambda x: (-x["score"], x["node_id"]))
    selected_entries = [ns for ns in node_scores if ns["eligible"]][:top_k]
    below_threshold = [ns["node_id"] for ns in node_scores if not ns["eligible"] and ns["score"] > 0]
    return node_scores, selected_entries, below_threshold


# ---------------------------------------------------------------------------
# C. Dependency/provenance/safety closure with budget
# ---------------------------------------------------------------------------

def _expand_dependencies(
    selected_ids: set[str],
    nodes_by_id: dict[str, dict[str, Any]],
    adj: dict[str, set[str]],
    max_closure_nodes: int,
) -> tuple[set[str], list[dict[str, str]], bool, bool, set[str]]:
    """Compute one deterministic dependency/provenance/safety closure under a hard budget."""
    if not isinstance(max_closure_nodes, int) or isinstance(max_closure_nodes, bool) or max_closure_nodes < 1:
        raise GraphError("invalid_closure_budget", "max_closure_nodes must be a positive integer")
    if len(selected_ids) > max_closure_nodes:
        raise GraphError("closure_budget_exceeded", f"{len(selected_ids)} seeds exceed closure budget {max_closure_nodes}")

    expanded = set(selected_ids)
    reasons: list[dict[str, str]] = []
    worklist = sorted(selected_ids)
    unexpanded: set[str] = set()
    while worklist:
        current = worklist.pop(0)
        node = nodes_by_id[current]
        edges: list[tuple[str, str, str]] = []
        for dep in node["dependencies"]:
            edges.append((dep["target_node_id"], dep["relation_type"], dep["reason"]))
        for rel in node["relations"]:
            if rel["relation_type"] in {"safety_requires", "provenance_chain"}:
                edges.append((rel["target_node_id"], rel["relation_type"], rel["reason"]))
        for target, relation_type, reason in sorted(edges):
            if target in expanded:
                continue
            if len(expanded) >= max_closure_nodes:
                unexpanded.add(target)
                continue
            expanded.add(target)
            worklist.append(target)
            worklist.sort()
            reasons.append({
                "node_id": target,
                "reason": f"dependency: {relation_type} - {reason}",
                "triggered_by": current,
            })
    cycle = _detect_cycle({node_id: adj.get(node_id, set()) & expanded for node_id in expanded})
    return expanded, reasons, cycle is not None, bool(unexpanded), unexpanded


# ---------------------------------------------------------------------------
# C2. Residual bank and revisit
# ---------------------------------------------------------------------------

def _residual_revisit(
    residual_bank: dict[str, Any] | None,
    nodes_by_id: dict[str, dict[str, Any]],
    lexical_ids: set[str],
    vector_ids: set[str],
    query_text: str,
    intent_tokens: list[str],
    graph_id: str,
    revisit_top_k: int,
) -> dict[str, Any]:
    """Reselect relevant prior-only nodes; current-candidate overlap is not a revisit."""
    if not isinstance(revisit_top_k, int) or isinstance(revisit_top_k, bool) or revisit_top_k < 1:
        raise GraphError("invalid_revisit_top_k", "revisit_top_k must be a positive integer")
    if residual_bank is not None and not isinstance(residual_bank, dict):
        raise GraphError("malformed_residual_bank", "residual bank must be a JSON object")
    bank_provided = residual_bank is not None and bool(residual_bank.get("entries"))
    bank_version_in = residual_bank.get("bank_version", 0) if residual_bank else 0
    if residual_bank is not None:
        validate_instance(residual_bank, _schema("residual-bank.v1.schema.json"))
        if residual_bank["graph_id"] != graph_id:
            raise GraphError("residual_graph_mismatch", "residual bank graph_id does not match current graph")

    current_candidates = lexical_ids | vector_ids
    normalized_query = _normalize(query_text)
    latest_by_node: dict[str, dict[str, Any]] = {}
    for entry in (residual_bank or {}).get("entries", []):
        if entry["node_id"] not in nodes_by_id:
            raise GraphError("residual_unknown_node", f"residual bank references unknown node {entry['node_id']}")
        latest_by_node[entry["node_id"]] = entry

    scored: list[tuple[int, str, list[str]]] = []
    excluded_by_anti: set[str] = set()
    for node_id, entry in latest_by_node.items():
        if node_id in current_candidates:
            continue
        node = nodes_by_id[node_id]
        anti_hits = [term for term in node.get("anti_triggers", []) if _normalize(term) in normalized_query]
        if anti_hits:
            excluded_by_anti.add(node_id)
            continue
        hits: list[str] = []
        score = 0
        for trigger in node.get("triggers", []):
            term = _normalize(trigger["term"])
            if term and term in normalized_query:
                hits.append(trigger["term"])
                score += int(trigger["weight"])
        searchable = _normalize(f"{node.get('title', '')} {node.get('content', '')}")
        token_hits = [token for token in intent_tokens if token in searchable]
        score += len(token_hits)
        hits.extend(f"token:{token}" for token in token_hits)
        if score > 0:
            scored.append((score, node_id, sorted(set(hits))))
    scored.sort(key=lambda row: (-row[0], row[1]))
    selected = scored[:revisit_top_k]
    revisited_ids = {node_id for _, node_id, _ in selected}
    revisited = [
        {
            "node_id": node_id,
            "from_stage_id": latest_by_node[node_id]["stage_id"],
            "revisit_score": score,
            "reason": f"residual bank reselection from current query evidence: {', '.join(hits)}",
        }
        for score, node_id, hits in selected
    ]

    active_experts = {nodes_by_id[node_id]["expert_id"] for node_id in current_candidates | revisited_ids}
    excluded_siblings = []
    for node_id in sorted(latest_by_node):
        if node_id in current_candidates or node_id in revisited_ids:
            continue
        node = nodes_by_id[node_id]
        if node_id in excluded_by_anti or node["expert_id"] in active_experts:
            excluded_siblings.append({
                "node_id": node_id,
                "reason": "anti-triggered or irrelevant sibling not supported by current query",
            })

    return {
        "bank_provided": bank_provided,
        "bank_version_in": bank_version_in,
        "revisited": revisited,
        "excluded_siblings": excluded_siblings,
    }


def _build_residual_bank(
    residual_bank: dict[str, Any] | None,
    final_ids: set[str],
    origin_map: dict[str, list[str]],
    query_id: str,
    graph_id: str,
) -> dict[str, Any]:
    """Append the exact final selected state without deleting prior history."""
    previous_entries = list((residual_bank or {}).get("entries", []))
    new_entries = [
        {
            "stage_id": "graph_route",
            "query_id": query_id,
            "node_id": node_id,
            "selection_reason": f"selected via {'+'.join(sorted(origin_map.get(node_id, ['unknown'])))}",
        }
        for node_id in sorted(final_ids)
    ]
    return {
        "contract_version": GRAPH_CONTRACT_VERSION,
        "bank_version": (residual_bank or {}).get("bank_version", 0) + 1,
        "graph_id": graph_id,
        "entries": previous_entries + new_entries,
    }


# ---------------------------------------------------------------------------
# D. Scoped safety expansion
# ---------------------------------------------------------------------------

def _scoped_safety(
    nodes_by_id: dict[str, dict[str, Any]],
    risk_domains: list[str],
    safety_config: dict[str, Any],
) -> tuple[dict[str, Any], set[str]]:
    """Return only mandatory global/risk safety seeds for the single closure pass."""
    baseline_checks = safety_config.get("baseline_checks", [])
    global_ids = list(safety_config.get("global_invariant_node_ids", []))
    risk_index = safety_config.get("risk_domain_index", {})
    seeds: set[str] = set()
    expansions: list[dict[str, str]] = []
    risk_included: list[str] = []
    for node_id in global_ids:
        if node_id not in nodes_by_id:
            raise GraphError("missing_safety_node", f"configured global safety node missing: {node_id}")
        seeds.add(node_id)
        expansions.append({"node_id": node_id, "expansion_reason": "global_invariant: mandatory route seed"})
    for domain in risk_domains:
        for node_id in risk_index.get(domain, []):
            if node_id not in nodes_by_id:
                raise GraphError("missing_safety_node", f"configured risk safety node missing: {node_id}")
            seeds.add(node_id)
            risk_included.append(node_id)
            expansions.append({"node_id": node_id, "expansion_reason": f"risk_domain:{domain}: mandatory route seed"})
    return {
        "baseline_checks_run": baseline_checks,
        "scoped_expansions": expansions,
        "global_invariant_included": sorted(set(global_ids)),
        "risk_domain_included": sorted(set(risk_included)),
    }, seeds


# ---------------------------------------------------------------------------
# E. Full graph route
# ---------------------------------------------------------------------------

def route_graph(
    graph_registry_path: Path,
    request: dict[str, Any],
    residual_bank: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute full multi-stage sparse graph routing with vector-first candidate union."""
    graph_registry_path = graph_registry_path.resolve()
    graph = load_json(graph_registry_path)
    validate_instance(graph, _schema("graph-registry.v1.schema.json"))
    if graph["contract_version"] != GRAPH_CONTRACT_VERSION:
        raise GraphError("schema_version_mismatch", "graph registry contract version mismatch")

    graph_id = graph["graph_id"]

    # Validate base registry
    workspace = graph_registry_path.parent.parent

    base_registry_path = workspace / "build" / "expert-registry.v2.json"
    if not base_registry_path.is_file():
        raise GraphError("missing_base_registry", "base v2 expert-registry not found")
    base_registry = load_json(base_registry_path)
    base_registry_file_sha = _sha256_bytes(base_registry_path.read_bytes())
    if base_registry_file_sha != graph["base_registry_sha256"]:
        raise GraphError("base_registry_mismatch", "graph registry base_registry_sha256 does not match")

    # Load manifest and chunks for provenance validation
    manifest_path = workspace / "source-manifest.json"
    manifest = load_json(manifest_path)
    if _sha256_bytes(manifest_path.read_bytes()) != graph["source_manifest_sha256"]:
        raise GraphError("source_manifest_mismatch", "graph registry source manifest binding does not match")
    chunks = {row["chunk_id"]: row for row in manifest["chunks"]}

    # Load and validate atomic nodes
    nodes = load_atomic_nodes(workspace)
    _validate_source_refs(nodes, chunks)
    adj = _validate_dependencies(nodes)
    cycle = _detect_cycle(adj)
    if cycle:
        raise GraphError("dependency_cycle", f"cycle detected in atomic nodes: {cycle}")

    nodes_by_id = {n["node_id"]: n for n in nodes}
    graph_node_ids = {node["node_id"] for node in graph["atomic_nodes"]}
    if set(nodes_by_id) != graph_node_ids:
        raise GraphError("graph_node_set_mismatch", "current atomic node set differs from graph registry")

    # Validate atom coverage and its exact graph binding.
    validate_atom_coverage(workspace)
    coverage_path = workspace / "distilled" / "atom-coverage.json"
    if _sha256_bytes(coverage_path.read_bytes()) != graph["atom_coverage_sha256"]:
        raise GraphError("atom_coverage_mismatch", "graph registry atom coverage binding does not match")

    # Validate atom paths match graph registry
    atoms_dir = workspace / "distilled" / "atoms"
    for gn in graph["atomic_nodes"]:
        atom_path = workspace_path(workspace, gn["atom_path"])
        if not atom_path.is_file():
            raise GraphError("missing_atom_file", f"atom file missing: {gn['atom_path']}")
        if _sha256_bytes(atom_path.read_bytes()) != gn["atom_sha256"]:
            raise GraphError("atom_hash_mismatch", f"atom file changed: {gn['atom_path']}")

    # Validate vector index
    vector_config = graph["vector_config"]
    vector_routing = vector_config.get("vector_routing", "disabled")
    channels = vector_config.get("channels", [])
    if vector_routing != "disabled":
        validate_channel_config(channels)
        vec_index_path_str = vector_config.get("vector_index_path", "")
        vec_index_sha = vector_config.get("vector_index_sha256", "")
        if vec_index_path_str:
            vec_index_path = workspace_path(workspace, vec_index_path_str)
            if not vec_index_path.is_file():
                raise GraphError("missing_vector_index", f"vector index file missing: {vec_index_path_str}")
            actual_sha = _sha256_bytes(vec_index_path.read_bytes())
            if vec_index_sha and actual_sha != vec_index_sha:
                raise GraphError("vector_index_mismatch", "vector index sha256 mismatch")
            vector_index = load_json(vec_index_path)
            validate_instance(vector_index, _schema("vector-index.v1.schema.json"))
            if vector_index["graph_id"] != graph_id or vector_index["channels"] != channels:
                raise GraphError("vector_index_binding_mismatch", "vector index graph/channel metadata differs from graph registry")
            expected_vectors = []
            for node in nodes:
                for vec in validate_node_vectors(node, channels):
                    expected_vectors.append({"node_id": node["node_id"], **vec})
            key = lambda row: (row["node_id"], row["channel_name"])
            if sorted(expected_vectors, key=key) != sorted(vector_index["node_vectors"], key=key):
                raise GraphError("vector_index_binding_mismatch", "vector index contents differ from atomic node vectors")

    # Resolve backend if configured
    backend_type = vector_config.get("default_backend", "none")
    if vector_routing != "disabled" and backend_type != "none":
        resolve_backend(backend_type)  # fail closed if unavailable

    # Parse and strictly bound request-controlled routing values.
    if not isinstance(request, dict):
        raise GraphError("malformed_input", "request must be an object")
    query = request.get("query", "")
    if not isinstance(query, str) or not query.strip():
        raise GraphError("malformed_input", "query must contain non-whitespace text")
    query_id = request.get("query_id", "graph-route")
    if not isinstance(query_id, str) or not query_id.strip():
        raise GraphError("malformed_input", "query_id must be a non-empty string")
    raw_risk_domains = request.get("risk_domains", [])
    if not isinstance(raw_risk_domains, list) or any(not isinstance(value, str) or not value.strip() for value in raw_risk_domains):
        raise GraphError("malformed_input", "risk_domains must be a list of non-empty strings")
    risk_domains = sorted(set(raw_risk_domains))
    policy = graph["routing_policy"]

    def bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
        value = request.get(name, default)
        if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
            raise GraphError("malformed_input", f"{name} must be an integer in [{minimum}, {maximum}]")
        return value

    top_k = bounded_int("top_k", policy["default_top_k"], 1, policy["max_top_k"])
    minimum_score = bounded_int("minimum_score", policy["minimum_score"], 0, 1000000)
    max_closure = bounded_int("max_closure_nodes", policy["max_closure_nodes"], 1, policy["max_closure_nodes"])
    vector_top_k = bounded_int("vector_top_k", policy["vector_top_k"], 1, policy["max_top_k"])
    revisit_top_k = policy["revisit_top_k"]
    intent_tokens = _extract_intent_tokens(query)

    audit_log: list[dict[str, Any]] = []
    seq = 0

    # --- Stage 1: Lexical domain routing ---
    domain_scores, selected_domains = _stage1_domain_route(nodes, intent_tokens, risk_domains)
    seq += 1
    audit_log.append({"sequence": seq, "event": "stage1_domain_route", "details": {
        "domain_scores": domain_scores,
        "selected_domains": selected_domains,
    }})

    # --- Stage 2: Lexical atomic selection ---
    node_scores, selected_entries, below_threshold = _stage2_atomic_route(
        nodes, selected_domains, intent_tokens, minimum_score, top_k
    )
    lexical_ids = {e["node_id"] for e in selected_entries}
    seq += 1
    audit_log.append({"sequence": seq, "event": "stage2_atomic_route", "details": {
        "candidate_count": len([n for n in nodes if n["expert_id"] in selected_domains]),
        "lexical_selected_ids": sorted(lexical_ids),
        "below_threshold_count": len(below_threshold),
    }})

    # --- Vector stage (B2) - BEFORE closure ---
    vector_stage: dict[str, Any] = {
        "mode": "disabled",
        "backend_type": backend_type,
        "query_vector_provided": False,
        "channels_used": [],
        "candidate_vectors_scored": 0,
        "vector_candidates": [],
        "vector_reranked_ids": [],
        "vector_exclusions": [],
    }

    vector_ids: set[str] = set()

    if vector_routing != "disabled":
        query_vectors = request.get("query_vectors")
        if "query_vectors" in request and not isinstance(query_vectors, dict):
            raise GraphError("malformed_input", "query_vectors must be an object keyed by configured channel")
        if isinstance(query_vectors, dict) and any(not isinstance(name, str) or not name.strip() for name in query_vectors):
            raise GraphError("malformed_input", "query_vectors channel names must be non-empty strings")
        if query_vectors:
            # Unknown channels must fail closed.  Pass the complete graph
            # configuration to scoring so a query that uses one channel does
            # not make valid node vectors from other configured channels look
            # like metadata errors.
            configured_channels = {ch["channel_name"] for ch in channels}
            unknown_channels = sorted(set(query_vectors) - configured_channels)
            if unknown_channels:
                raise GraphError("unknown_channel", f"query vectors contain unknown channels: {unknown_channels}")
            valid_channels = [ch for ch in channels if ch["channel_name"] in query_vectors]
            if not valid_channels:
                raise GraphError("no_valid_channels", "query vectors don't match any configured channel")

            vector_stage["mode"] = "vector_and_lexical"
            vector_stage["query_vector_provided"] = True
            vector_stage["channels_used"] = [ch["channel_name"] for ch in valid_channels]

            vec_result = score_vector_candidates(
                nodes, query_vectors, channels, vector_top_k
            )
            vector_stage["candidate_vectors_scored"] = vec_result["candidate_vectors_scored"]
            vector_stage["vector_candidates"] = vec_result["vector_candidates"]
            vector_stage["vector_exclusions"] = vec_result["vector_exclusions"]

            # Symbolic reranking
            anti_trigger_set = set()
            for node in nodes:
                for a in node.get("anti_triggers", []):
                    if _normalize(a) in " ".join(intent_tokens):
                        anti_trigger_set.add(a.lower())

            rerank_result = symbolic_rerank(
                vec_result["vector_candidates"],
                nodes_by_id,
                intent_tokens,
                anti_trigger_set,
                graph["safety_config"],
                risk_domains,
            )
            vector_stage["vector_reranked_ids"] = rerank_result["reranked_ids"]
            vector_stage["vector_exclusions"] = vec_result["vector_exclusions"] + rerank_result["exclusions"]
            vector_ids = set(rerank_result["reranked_ids"])

        elif vector_routing == "required":
            raise GraphError("required_vector_missing", "vector routing is required but no query_vectors provided")
        else:
            vector_stage["mode"] = "lexical_only"

    seq += 1
    audit_log.append({"sequence": seq, "event": "vector_addressing_stage", "details": {
        "mode": vector_stage["mode"],
        "backend": vector_stage["backend_type"],
        "candidates_scored": vector_stage["candidate_vectors_scored"],
        "vector_ids": sorted(vector_ids),
    }})

    # --- Candidate union ---
    candidate_union: list[dict[str, Any]] = []
    all_candidate_ids = lexical_ids | vector_ids
    for nid in sorted(all_candidate_ids):
        origins = []
        if nid in lexical_ids:
            origins.append("lexical")
        if nid in vector_ids:
            origins.append("vector")
        candidate_union.append({"node_id": nid, "origins": origins})

    seq += 1
    audit_log.append({"sequence": seq, "event": "candidate_union", "details": {
        "total_candidates": len(candidate_union),
        "lexical_only": len(lexical_ids - vector_ids),
        "vector_only": len(vector_ids - lexical_ids),
        "both": len(lexical_ids & vector_ids),
    }})

    # --- Residual revisit ---
    residual_revisit_output = _residual_revisit(
        residual_bank, nodes_by_id, lexical_ids, vector_ids, query, intent_tokens, graph_id, revisit_top_k
    )
    revisit_ids = {row["node_id"] for row in residual_revisit_output["revisited"]}
    all_candidate_ids.update(revisit_ids)
    for node_id in sorted(revisit_ids):
        candidate_union.append({"node_id": node_id, "origins": ["residual_revisit"]})
    candidate_union.sort(key=lambda row: row["node_id"])

    seq += 1
    audit_log.append({"sequence": seq, "event": "residual_revisit", "details": {
        "bank_provided": residual_revisit_output["bank_provided"],
        "revisited_count": len(revisit_ids),
        "excluded_siblings": len(residual_revisit_output["excluded_siblings"]),
    }})

    # Mandatory safety seeds participate in the same single bounded closure.
    safety_output, safety_seed_ids = _scoped_safety(nodes_by_id, risk_domains, graph["safety_config"])
    fallback_activated = not lexical_ids and not vector_ids and not revisit_ids
    if fallback_activated and not safety_seed_ids:
        raise GraphError("missing_safety_fallback", "no route candidates and no configured scoped safety fallback")
    closure_seeds = all_candidate_ids | safety_seed_ids
    expanded_ids, expansion_reasons, cycle_detected, closure_truncated, unexpanded = _expand_dependencies(
        closure_seeds, nodes_by_id, adj, max_closure
    )
    if cycle_detected:
        raise GraphError("dependency_cycle", "cycle detected during closure")
    if closure_truncated:
        raise GraphError("closure_budget_exceeded", f"closure budget {max_closure} cannot include required nodes: {sorted(unexpanded)}")

    # Record red-line nodes reached through scoped safety/provenance dependencies.
    safety_seed_set = set(safety_seed_ids)
    for reason in expansion_reasons:
        node_id = reason["node_id"]
        if nodes_by_id[node_id]["node_kind"] == "red_line" and node_id not in safety_seed_set:
            safety_output["scoped_expansions"].append({
                "node_id": node_id,
                "expansion_reason": reason["reason"],
            })

    seq += 1
    audit_log.append({"sequence": seq, "event": "single_bounded_closure", "details": {
        "seed_count": len(closure_seeds),
        "expanded_count": len(expansion_reasons),
        "budget": max_closure,
        "final_count": len(expanded_ids),
    }})

    origin_map: dict[str, list[str]] = {}
    for candidate in candidate_union:
        origin_map[candidate["node_id"]] = list(candidate["origins"])
    for node_id in sorted(safety_seed_ids):
        origin_map.setdefault(node_id, []).append("safety")
    for reason in expansion_reasons:
        origin_map.setdefault(reason["node_id"], []).append("closure")

    fallback_node_ids = sorted(safety_seed_ids) if fallback_activated else []
    if fallback_activated:
        for node_id in fallback_node_ids:
            origin_map.setdefault(node_id, []).append("fallback")
    fallback = {
        "activated": fallback_activated,
        "reason": "no_lexical_vector_or_residual_candidates" if fallback_activated else "",
        "fallback_node_ids": fallback_node_ids,
    }

    # Build exact final selected state only after every seed and closure expansion.
    selected_node_outputs: list[dict[str, Any]] = []
    for node_id in sorted(expanded_ids):
        node = nodes_by_id[node_id]
        ref = node["source_ref"]
        chunk_ids: list[str] = []
        provenance_trail: list[dict[str, Any]] = []
        if ref["ref_type"] == "chunk" and ref.get("chunk_id"):
            chunk_ids.append(ref["chunk_id"])
            provenance_trail.append({
                "chunk_id": ref["chunk_id"],
                "source_id": ref.get("source_id", ""),
                "start_line": ref.get("start_line", 0),
                "end_line": ref.get("end_line", 0),
            })
        graph_node = next(row for row in graph["atomic_nodes"] if row["node_id"] == node_id)
        selected_node_outputs.append({
            "node_id": node_id,
            "node_kind": node["node_kind"],
            "expert_id": node["expert_id"],
            "title": node["title"],
            "origins": sorted(set(origin_map.get(node_id, ["unknown"]))),
            "atom_path": graph_node["atom_path"],
            "atom_sha256": graph_node["atom_sha256"],
            "l3_path": graph_node["l3_path"],
            "chunk_ids": chunk_ids,
            "provenance_trail": provenance_trail,
        })
    rejected_ids = set(nodes_by_id) - expanded_ids
    rejected_nodes = [{"node_id": node_id, "reason": "not_selected_or_expanded"} for node_id in sorted(rejected_ids)]
    new_bank = _build_residual_bank(residual_bank, expanded_ids, origin_map, query_id, graph_id)
    validate_instance(new_bank, _schema("residual-bank.v1.schema.json"))

    # --- Load plan ---
    workspace_posix = workspace.as_posix()
    files_to_load: list[str] = []
    file_checksums: list[dict[str, Any]] = []
    seen_files: set[str] = set()

    # Shared core
    shared_core_path = workspace / "distilled" / "shared-core.md"
    sc_posix = shared_core_path.as_posix()
    files_to_load.append(sc_posix)
    file_checksums.append({"path": sc_posix, "sha256": _sha256_bytes(shared_core_path.read_bytes()), "role": "shared_core"})
    seen_files.add(sc_posix)

    for sno in selected_node_outputs:
        # Atom file
        if sno["atom_path"]:
            ap = workspace_path(workspace, sno["atom_path"]).as_posix()
            if ap not in seen_files:
                files_to_load.append(ap)
                file_checksums.append({"path": ap, "sha256": sno["atom_sha256"], "role": "atomic_node"})
                seen_files.add(ap)
        # L3 file
        if sno["l3_path"]:
            l3 = workspace_path(workspace, sno["l3_path"]).as_posix()
            if l3 not in seen_files:
                files_to_load.append(l3)
                l3_sha = _sha256_bytes(workspace_path(workspace, sno["l3_path"]).read_bytes())
                file_checksums.append({"path": l3, "sha256": l3_sha, "role": "expert_l3_depth_view"})
                seen_files.add(l3)

    source_chunks: list[dict[str, Any]] = []
    seen_chunks: set[str] = set()
    for sno in selected_node_outputs:
        for cid in sno["chunk_ids"]:
            if cid not in seen_chunks and cid in chunks:
                seen_chunks.add(cid)
                c = chunks[cid]
                cp = workspace_path(workspace, c["path"]).as_posix()
                source_chunks.append({
                    "chunk_id": cid,
                    "path": cp,
                    "sha256": c["sha256"],
                    "source_id": c["source_id"],
                    "start_line": c["start_line"],
                    "end_line": c["end_line"],
                })

    load_plan = {
        "path_base": workspace_posix,
        "files_to_load": files_to_load,
        "file_checksums": file_checksums,
        "source_chunks": source_chunks,
        "node_count": len(selected_node_outputs),
        "chunk_count": len(source_chunks),
        "file_count": len(files_to_load),
    }

    # --- Status ---
    status = "fallback_safety_only" if fallback_activated else "selected"

    # --- Validate output against schema ---
    output = {
        "contract_version": GRAPH_CONTRACT_VERSION,
        "graph_id": graph_id,
        "query_id": query_id,
        "status": status,
        "query_context": {
            "normalized_query": _normalize(query),
            "intent_tokens": intent_tokens,
            "explicit_risk_domains": risk_domains,
            "stage_id": "graph_route",
        },
        "stage1_domain_route": {
            "stage_id": "coarse_domain",
            "candidate_domains": sorted(domain_scores.keys()),
            "selected_domains": selected_domains,
            "domain_scores": domain_scores,
        },
        "stage2_atomic_route": {
            "stage_id": "atomic_selection",
            "candidate_nodes": len([n for n in nodes if n["expert_id"] in selected_domains]),
            "lexical_selected_ids": sorted(lexical_ids),
            "node_scores": [
                {"node_id": ns["node_id"], "score": ns["score"], "hits": ns["hits"],
                 "anti_hits": ns["anti_hits"], "eligible": ns["eligible"]}
                for ns in node_scores
            ],
            "below_threshold": below_threshold,
        },
        "vector_stage": vector_stage,
        "candidate_union": candidate_union,
        "residual_revisit": residual_revisit_output,
        "closure": {
            "expanded_node_ids": sorted(expanded_ids),
            "expansion_reasons": expansion_reasons,
            "cycle_detected": cycle_detected,
            "budget": max_closure,
            "closure_truncated": closure_truncated,
            "unexpanded_node_ids": sorted(unexpanded),
        },
        "safety": safety_output,
        "selected_nodes": selected_node_outputs,
        "rejected_nodes": rejected_nodes,
        "fallback": fallback,
        "load_plan": load_plan,
        "residual": new_bank,
        "audit_log": audit_log,
    }
    validate_instance(output, _schema("atomic-route-output.v1.schema.json"))
    return output


# ---------------------------------------------------------------------------
# Graph registry building
# ---------------------------------------------------------------------------

def build_graph_registry(workspace: Path) -> Path:
    """Build graph-registry.v1.json and vector-index.v1.json from workspace."""
    from pipeline import validate_distillation, build_registry  # noqa: delayed import

    workspace = workspace.resolve()

    # Revalidate current source/distillation state and deterministically rebuild the bound base registry.
    validate_distillation(workspace)
    build_registry(workspace)
    base_registry_path = workspace / "build" / "expert-registry.v2.json"
    base_registry = load_json(base_registry_path)
    base_registry_sha = _sha256_bytes(base_registry_path.read_bytes())

    # Validate atom coverage
    coverage = validate_atom_coverage(workspace)
    coverage_sha = _sha256_bytes((workspace / "distilled" / "atom-coverage.json").read_bytes())

    # Load atomic nodes
    nodes = load_atomic_nodes(workspace)
    manifest = load_json(workspace / "source-manifest.json")
    manifest_sha = _sha256_bytes((workspace / "source-manifest.json").read_bytes())
    chunks = {row["chunk_id"]: row for row in manifest["chunks"]}
    _validate_source_refs(nodes, chunks)
    adj = _validate_dependencies(nodes)
    cycle = _detect_cycle(adj)
    if cycle:
        raise GraphError("dependency_cycle", f"cycle in atomic nodes: {cycle}")

    # Build dependency edges
    dependency_edges: list[dict[str, Any]] = []
    for node in nodes:
        for dep in node["dependencies"]:
            dependency_edges.append({
                "source_node_id": node["node_id"],
                "target_node_id": dep["target_node_id"],
                "edge_origin": "dependency",
                "relation_type": dep["relation_type"],
                "reason": dep["reason"],
            })
        for rel in node["relations"]:
            dependency_edges.append({
                "source_node_id": node["node_id"],
                "target_node_id": rel["target_node_id"],
                "edge_origin": "relation",
                "relation_type": rel["relation_type"],
                "reason": rel["reason"],
            })

    # Build domain index
    domain_index: dict[str, list[str]] = {}
    for node in nodes:
        domain_index.setdefault(node["expert_id"], []).append(node["node_id"])

    # Build risk domain index
    risk_domain_index: dict[str, list[str]] = {}
    global_invariant_node_ids: list[str] = []
    for node in nodes:
        if node.get("global_invariant"):
            global_invariant_node_ids.append(node["node_id"])
        for rd in node.get("risk_domains", []):
            risk_domain_index.setdefault(rd, []).append(node["node_id"])

    # Build atomic nodes index for graph registry
    base_experts = {e["expert_id"]: e for e in base_registry["experts"]}
    atoms_dir = workspace / "distilled" / "atoms"
    atomic_nodes_index: list[dict[str, Any]] = []
    for node in sorted(nodes, key=lambda n: n["node_id"]):
        # Resolve l3_path from base registry
        expert = base_experts.get(node["expert_id"])
        l3_path = ""
        if expert and expert.get("l3_files"):
            l3_path = expert["l3_files"][0]["path"]

        # Atom file path and hash - find file by loading each to match node_id.
        atom_file = atoms_dir / f"{node['node_id']}.json"
        if not atom_file.is_file():
            # Curated bundles may use human-readable filenames; never turn a
            # missing binding into an incidental FileNotFoundError.
            for p in sorted(atoms_dir.glob("*.json")):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if data.get("node_id") == node["node_id"]:
                        atom_file = p
                        break
                except (json.JSONDecodeError, OSError):
                    pass
        if not atom_file.is_file() or atom_file.is_symlink():
            raise GraphError("missing_atom_file", f"no regular atom file is bound to node: {node['node_id']}")
        atom_rel = str(atom_file.relative_to(workspace))
        atom_sha = _sha256_bytes(atom_file.read_bytes())

        chunk_ids = []
        ref = node["source_ref"]
        if ref["ref_type"] == "chunk" and ref.get("chunk_id"):
            chunk_ids.append(ref["chunk_id"])

        atomic_nodes_index.append({
            "node_id": node["node_id"],
            "node_kind": node["node_kind"],
            "expert_id": node["expert_id"],
            "routing_priority": node["routing_priority"],
            "title": node["title"],
            "one_liner": node["content"][:120] if len(node["content"]) > 120 else node["content"],
            "trigger_terms": node["triggers"],
            "anti_triggers": node["anti_triggers"],
            "safety_red_lines": node["safety_red_lines"],
            "validation_state": node["validation_state"],
            "global_invariant": node.get("global_invariant", False),
            "risk_domains": node.get("risk_domains", []),
            "atom_path": atom_rel,
            "atom_sha256": atom_sha,
            "l3_path": l3_path,
            "chunk_ids": chunk_ids,
        })

    # Build vector index
    channels = [
        {"channel_name": "semantic", "dimension": 4, "model_id": "synthetic_fixture", "model_version": "1.0.0", "weight": 1.0},
        {"channel_name": "task", "dimension": 3, "model_id": "synthetic_fixture", "model_version": "1.0.0", "weight": 0.5},
        {"channel_name": "risk", "dimension": 3, "model_id": "synthetic_fixture", "model_version": "1.0.0", "weight": 0.3},
    ]

    validate_channel_config(channels)
    node_vectors: list[dict[str, Any]] = []
    for node in nodes:
        for vec in validate_node_vectors(node, channels):
            node_vectors.append({
                "node_id": node["node_id"],
                "channel_name": vec["channel_name"],
                "dimension": vec["dimension"],
                "model_id": vec["model_id"],
                "model_version": vec["model_version"],
                "values": vec["values"],
            })

    graph_identity = {
        "base_registry_sha256": base_registry_sha,
        "source_manifest_sha256": manifest_sha,
        "atom_coverage_sha256": coverage_sha,
        "atomic_nodes": atomic_nodes_index,
        "dependency_edges": dependency_edges,
        "domain_index": domain_index,
        "risk_domain_index": risk_domain_index,
        "global_invariant_node_ids": global_invariant_node_ids,
        "channels": channels,
    }
    graph_id = f"graph-{_sha256_bytes(_canonical_bytes(graph_identity))[:16]}"

    vector_index = {
        "contract_version": GRAPH_CONTRACT_VERSION,
        "graph_id": graph_id,
        "channels": channels,
        "node_vectors": node_vectors,
    }
    validate_instance(vector_index, _schema("vector-index.v1.schema.json"))

    vector_index_path = workspace / "build" / "vector-index.v1.json"
    _write_json(vector_index_path, vector_index)
    vector_index_sha = _sha256_bytes(vector_index_path.read_bytes())

    # Build graph registry (no build_ts - deterministic)
    graph_registry = {
        "contract_version": GRAPH_CONTRACT_VERSION,
        "graph_id": graph_id,
        "base_registry_id": base_registry["registry_id"],
        "base_build_id": base_registry["build_id"],
        "base_registry_sha256": base_registry_sha,
        "source_manifest_sha256": manifest_sha,
        "atom_coverage_sha256": coverage_sha,
        "atomic_nodes": atomic_nodes_index,
        "dependency_edges": dependency_edges,
        "domain_index": domain_index,
        "routing_policy": {
            "minimum_score": 2,
            "default_top_k": 5,
            "max_top_k": 10,
            "vector_top_k": 5,
            "max_closure_nodes": 20,
            "revisit_top_k": 3,
        },
        "safety_config": {
            "baseline_checks": ["provenance_integrity", "dependency_completeness", "cycle_absence"],
            "global_invariant_node_ids": global_invariant_node_ids,
            "risk_domain_index": risk_domain_index,
        },
        "provenance_revisit_policy": {
            "retain_query_context": True,
            "trace_expansion_reasons": True,
            "residual_bank_supported": True,
        },
        "vector_config": {
            "vector_routing": "optional",
            "default_backend": "none",
            "channels": channels,
            "vector_index_path": str(vector_index_path.relative_to(workspace)),
            "vector_index_sha256": vector_index_sha,
        },
    }
    validate_instance(graph_registry, _schema("graph-registry.v1.schema.json"))

    graph_path = workspace / "build" / "graph-registry.v1.json"
    _write_json(graph_path, graph_registry)
    return graph_path


def workspace_path(workspace: Path, relative: str) -> Path:
    """Resolve a relative path within the workspace, rejecting escapes."""
    candidate = (workspace / relative).resolve()
    try:
        candidate.relative_to(workspace.resolve())
    except ValueError as exc:
        raise GraphError("unsafe_workspace_path", f"path escapes workspace: {relative}") from exc
    return candidate
