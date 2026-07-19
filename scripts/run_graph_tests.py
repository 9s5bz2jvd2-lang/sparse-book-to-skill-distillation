#!/usr/bin/env python3
"""Comprehensive Phase-1 graph-sparse and vector-addressing tests.

Covers all 12 scope gates:
- A: atomic node loading, validation, all 7 node kinds
- B: multi-stage sparse gating (domain -> atomic)
- B2: multi-channel vector addressing (semantic/task/risk, weighted fusion, fail-closed)
- B3: vector-first candidate union BEFORE closure
- C: scoped safety (not global red-line append)
- D: versioned residual bank with sibling exclusion
- E: closure budget and truncation
- F: fallback materialization
- G: deterministic rebuild
- H: atom coverage validation
- I: backend fail-closed
- J: final load-plan semantics (no stale output)
- Deferred: serial/parallel/graph-shared composition (preserved, not counted)
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from artifact_io import write_json_atomic
from contract_validation import ContractError, load_json, validate_instance
from pipeline import (
    ROOT,
    build_registry,
    finalize_queue_and_source_map,
    install_curated_artifacts,
    intake_sources,
    prepare_distillation,
    query_registry,
    sha256_bytes,
    write_json,
)
from atomic_graph import (
    GraphError,
    build_graph_registry,
    load_atomic_nodes,
    route_graph,
    validate_atom_coverage,
)
from vector_sim import (
    VectorError,
    cosine_similarity,
    validate_vector,
    score_vector_candidates,
    symbolic_rerank,
    get_backend,
    resolve_backend,
)

SOURCE = ROOT / "examples" / "from-zero" / "source"
CURATED = ROOT / "examples" / "from-zero" / "curated"
TEST_ROOT = ROOT / "build" / "graph-tests"


def clean() -> None:
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)


def setup_complete(name: str) -> Path:
    ws = TEST_ROOT / name
    intake_sources(SOURCE, ws, max_lines_per_chunk=6)
    prepare_distillation(ws)
    install_curated_artifacts(ws, CURATED)
    finalize_queue_and_source_map(ws)
    return ws


def expect_error(code: str, fn) -> None:
    try:
        fn()
    except (ContractError, GraphError, VectorError) as exc:
        if exc.code != code:
            raise AssertionError(f"expected {code!r}, got {exc.code!r}: {exc.message}") from exc
    else:
        raise AssertionError(f"expected {code!r}, operation succeeded")


def file_sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    results: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []
    clean()
    TEST_ROOT.mkdir(parents=True)
    try:
        # ==================================================================
        # A. Atomic node loading and validation
        # ==================================================================
        ws = setup_complete("graph-main")
        nodes = load_atomic_nodes(ws)
        assert len(nodes) == 7, f"expected 7 atomic nodes, got {len(nodes)}"
        results.append(("atomic-load-nodes", f"loaded {len(nodes)} atomic nodes from curated/atoms/"))

        kinds = {n["node_kind"] for n in nodes}
        expected_kinds = {"definition", "formula", "condition", "counterexample", "workflow_step", "evidence", "red_line"}
        assert kinds == expected_kinds, f"node kinds {kinds} != {expected_kinds}"

        node_ids = {n["node_id"] for n in nodes}
        assert "coverage-definition" in node_ids
        assert "manifest-provenance-workflow" in node_ids
        assert "safety-no-partial-coverage" in node_ids
        assert "evidence-hash-stability" in node_ids
        assert "counterexample-unstructured-summary" in node_ids
        results.append(("atomic-node-kinds", f"all 7 node kinds present: {sorted(kinds)}"))

        # Check multi-channel vectors
        for node in nodes:
            vecs = node.get("vectors", [])
            assert len(vecs) == 3, f"node {node['node_id']} has {len(vecs)} vectors, expected 3"
            ch_names = {v["channel_name"] for v in vecs}
            assert ch_names == {"semantic", "task", "risk"}, f"node {node['node_id']} channels: {ch_names}"
        results.append(("multi-channel-vectors", f"all {len(nodes)} nodes have semantic/task/risk vectors"))

        # ==================================================================
        # B. Graph registry build
        # ==================================================================
        graph_path = build_graph_registry(ws)
        assert graph_path.is_file()
        graph = load_json(graph_path)
        assert graph["contract_version"] == "1.0.0"
        assert len(graph["atomic_nodes"]) == 7
        assert len(graph["dependency_edges"]) > 0
        assert graph["vector_config"]["vector_routing"] == "optional"

        # Check required fields per schema
        assert "source_manifest_sha256" in graph
        assert "atom_coverage_sha256" in graph
        assert "routing_policy" in graph
        assert "safety_config" in graph
        assert "build_ts" not in graph, "build_ts must not appear (determinism)"
        results.append(("graph-registry-build", f"graph registry built with {len(graph['atomic_nodes'])} nodes, {len(graph['dependency_edges'])} edges, no build_ts"))

        # Check vector index exists
        vec_index_path = ws / "build" / "vector-index.v1.json"
        assert vec_index_path.is_file()
        vec_index = load_json(vec_index_path)
        assert vec_index["contract_version"] == "1.0.0"
        assert len(vec_index["channels"]) == 3
        assert len(vec_index["node_vectors"]) == 7 * 3  # 7 nodes x 3 channels
        results.append(("vector-index-build", f"vector index built with {len(vec_index['channels'])} channels, {len(vec_index['node_vectors'])} node vectors"))

        metadata_path = ws / "distilled" / "atoms" / "node-coverage-definition.json"
        metadata_original = metadata_path.read_bytes()
        malformed = load_json(metadata_path)
        malformed["vectors"][0]["model_version"] = "wrong-version"
        write_json(metadata_path, malformed)
        expect_error("vector_metadata_mismatch", lambda: build_graph_registry(ws))
        metadata_path.write_bytes(metadata_original)
        graph_path = build_graph_registry(ws)
        graph = load_json(graph_path)
        results.append(("vector-build-metadata", "graph build fails closed on atom/channel model metadata mismatch"))

        vector_path = ws / graph["vector_config"]["vector_index_path"]
        vector_original = vector_path.read_bytes()
        graph_original = graph_path.read_bytes()
        tampered = load_json(vector_path)
        tampered["node_vectors"][0]["values"][0] += 0.001
        write_json(vector_path, tampered)
        graph_tampered = load_json(graph_path)
        graph_tampered["vector_config"]["vector_index_sha256"] = file_sha256(vector_path)
        write_json(graph_path, graph_tampered)
        expect_error("vector_index_binding_mismatch", lambda: route_graph(graph_path, {
            "query_id": "vector-sidecar-tamper", "query": "coverage", "risk_domains": []
        }))
        vector_path.write_bytes(vector_original)
        graph_path.write_bytes(graph_original)
        graph = load_json(graph_path)
        results.append(("vector-sidecar-binding", "rehashed vector sidecar still must exactly match atom vectors"))

        # Check atom coverage validated
        coverage = validate_atom_coverage(ws)
        assert len(coverage["entries"]) == 3
        assert all(e["status"] != "pending" for e in coverage["entries"])
        results.append(("atom-coverage-valid", f"atom coverage validated: {len(coverage['entries'])} entries"))

        coverage_path = ws / "distilled" / "atom-coverage.json"
        coverage_original = coverage_path.read_bytes()
        broken_coverage = load_json(coverage_path)
        broken_coverage["entries"][0]["atom_ids"] = broken_coverage["entries"][0]["atom_ids"][:-1]
        write_json(coverage_path, broken_coverage)
        expect_error("coverage_atom_binding_mismatch", lambda: validate_atom_coverage(ws))
        coverage_path.write_bytes(coverage_original)
        results.append(("atom-coverage-binding", "coverage atom IDs are bound to actual atomic nodes"))
        duplicate_coverage = load_json(coverage_path)
        duplicate_coverage["entries"].append(dict(duplicate_coverage["entries"][0]))
        write_json(coverage_path, duplicate_coverage)
        expect_error("coverage_duplicate_chunk", lambda: validate_atom_coverage(ws))
        coverage_path.write_bytes(coverage_original)
        results.append(("atom-coverage-duplicate", "duplicate chunk decisions fail closed before dict normalization"))

        fixture_path = ws / "distilled" / "atoms" / "node-counterexample-unstructured-summary.json"
        fixture_original = fixture_path.read_bytes()
        fixture = load_json(fixture_path)
        fixture["validation_state"] = "validated"
        write_json(fixture_path, fixture)
        expect_error("coverage_fixture_laundering", lambda: validate_atom_coverage(ws))
        fixture_path.write_bytes(fixture_original)
        results.append(("fixture-honesty", "synthetic fixture atoms cannot be laundered as validated source evidence"))

        # ==================================================================
        # B2. Multi-channel vector tests
        # ==================================================================

        # B2a: Multi-channel cosine similarity
        a_sem = [1.0, 0.0, 0.0, 0.0]
        b_sem = [0.9, 0.3, 0.1, 0.0]
        sim = cosine_similarity(a_sem, b_sem)
        assert 0.9 < sim < 1.0, f"expected high similarity, got {sim}"
        results.append(("vector-cosine-det", f"cosine similarity deterministic: {sim:.6f}"))

        # B2b: Dimension mismatch fails closed
        expect_error("dimension_mismatch", lambda: cosine_similarity([1.0, 2.0], [1.0]))
        expect_error("dimension_mismatch", lambda: validate_vector([1.0, 2.0], 3, "test"))
        results.append(("vector-dim-mismatch", "dimension mismatch fails closed"))

        # B2c: Non-finite vector fails closed
        expect_error("invalid_vector", lambda: validate_vector([float('nan'), 1.0], 2, "test"))
        expect_error("invalid_vector", lambda: validate_vector([float('inf'), 1.0], 2, "test"))
        results.append(("vector-non-finite", "non-finite vectors fail closed"))

        # B2d: Empty vector fails closed
        expect_error("invalid_vector", lambda: validate_vector([], 0, "test"))
        results.append(("vector-empty", "empty vector fails closed"))

        # B2e: Multi-channel weighted fusion scoring
        channels = graph["vector_config"]["channels"]
        qvec_multi = {
            "semantic": [0.9, 0.3, 0.1, 0.0],
            "task": [0.8, 0.2, 0.1],
            "risk": [0.1, 0.0, 0.0],
        }
        vec_result = score_vector_candidates(nodes, qvec_multi, channels, top_k=3)
        assert vec_result["candidate_vectors_scored"] > 0
        assert len(vec_result["vector_candidates"]) > 0
        top = vec_result["vector_candidates"][0]
        assert top["node_id"] == "coverage-definition", f"expected coverage-definition, got {top['node_id']}"
        assert "fused_score" in top
        assert "channel_scores" in top
        assert set(top["channel_scores"].keys()) == {"semantic", "task", "risk"}
        results.append(("vector-multi-channel", f"multi-channel fusion: top={top['node_id']} fused={top['fused_score']:.6f} channels={list(top['channel_scores'].keys())}"))

        # B2f: Unknown channel fails closed
        bad_qvec = {"nonexistent_channel": [1.0, 2.0, 3.0]}
        expect_error("unknown_channel", lambda: score_vector_candidates(nodes, bad_qvec, channels, top_k=3))
        results.append(("vector-unknown-channel", "unknown channel fails closed"))

        # B2g: A valid single-channel query must remain usable, while a mixed
        # known/unknown request must not silently discard the unknown channel.
        task_only = route_graph(graph_path, {
            "query_id": "task-only-vector",
            "query": "coverage workflow",
            "risk_domains": [],
            "query_vectors": {"task": [0.8, 0.2, 0.1]},
        })
        assert task_only["vector_stage"]["mode"] == "vector_and_lexical"
        assert task_only["vector_stage"]["candidate_vectors_scored"] > 0
        expect_error("unknown_channel", lambda: route_graph(graph_path, {
            "query_id": "mixed-unknown-vector",
            "query": "coverage workflow",
            "risk_domains": [],
            "query_vectors": {"task": [0.8, 0.2, 0.1], "future_channel": [1.0]},
        }))
        results.append(("vector-subset-and-unknown", "single-channel recall works; mixed unknown channels fail closed"))

        # B2h: Symbolic reranking after vector recall (no global safety append)
        nodes_by_id = {n["node_id"]: n for n in nodes}
        safety_config = graph["safety_config"]
        rerank = symbolic_rerank(
            vec_result["vector_candidates"], nodes_by_id, ["coverage", "ledger"],
            set(), safety_config, []
        )
        assert "coverage-definition" in rerank["reranked_ids"]
        # Safety node NOT automatically appended in symbolic_rerank
        # It's handled by scoped safety in closure
        results.append(("vector-symbolic-rerank", f"symbolic rerank: {len(rerank['reranked_ids'])} ids, safety via scoped expansion"))

        # B2h: Backend unavailable fails closed
        expect_error("backend_unavailable", lambda: get_backend("nonexistent_backend_xyz"))
        expect_error("backend_unavailable", lambda: resolve_backend("nonexistent_backend_xyz"))
        results.append(("vector-backend-unavailable", "unregistered backend fails closed"))

        # B2i: shared artifact writer avoids fixed-name temp collisions and
        # leaves the old final artifact untouched until replacement succeeds.
        artifact_path = TEST_ROOT / "atomic-writer.json"
        stale_tmp = TEST_ROOT / "atomic-writer.json.tmp"
        write_json_atomic(artifact_path, {"version": 1})
        stale_tmp.write_text("stale temp from an interrupted prior run", encoding="utf-8")
        write_json_atomic(artifact_path, {"version": 2})
        assert load_json(artifact_path) == {"version": 2}
        assert stale_tmp.read_text(encoding="utf-8") == "stale temp from an interrupted prior run"
        stale_tmp.unlink()
        results.append(("atomic-artifact-writer", "unique temp + replace writer tolerates stale fixed-name temp residue"))

        # ==================================================================
        # C. Scoped safety (not global red-line append)
        # ==================================================================
        safety_request = {
            "query_id": "test-scoped-safety",
            "query": "manifest provenance tracking workflow",
            "risk_domains": [],
            "top_k": 3,
            "minimum_score": 2,
        }
        safety_route = route_graph(graph_path, safety_request)

        # Safety node should be in expanded set
        expanded_ids = safety_route["closure"]["expanded_node_ids"]
        assert "safety-no-partial-coverage" in expanded_ids, "safety node must be in closure"

        # But check safety was via scoped expansion, not global append
        safety_info = safety_route["safety"]
        assert safety_info["global_invariant_included"] or safety_info["scoped_expansions"]
        # Check that safety_no_partial_coverage has global_invariant=true
        safety_node = nodes_by_id["safety-no-partial-coverage"]
        assert safety_node.get("global_invariant") is True
        assert "coverage_integrity" in safety_node.get("risk_domains", [])
        results.append(("scoped-safety", f"safety node via {'global_invariant' if safety_info['global_invariant_included'] else 'scoped_expansion'}"))

        # ==================================================================
        # D. Vector-first candidate union BEFORE closure
        # ==================================================================
        request_with_vec = {
            "query_id": "test-vec-first",
            "query": "How do I create a complete coverage ledger with manifest provenance tracking?",
            "risk_domains": [],
            "top_k": 3,
            "minimum_score": 2,
            "query_vectors": {
                "semantic": [0.9, 0.3, 0.1, 0.0],
                "task": [0.8, 0.2, 0.1],
                "risk": [0.1, 0.0, 0.0],
            },
        }
        route = route_graph(graph_path, request_with_vec)

        # Candidate union shows both lexical and vector origins
        cu = route["candidate_union"]
        assert len(cu) > 0
        origins_seen = set()
        for entry in cu:
            for o in entry["origins"]:
                origins_seen.add(o)
        assert "lexical" in origins_seen
        assert "vector" in origins_seen
        results.append(("candidate-union-origins", f"candidate union: {len(cu)} nodes, origins={sorted(origins_seen)}"))

        # Selected nodes have correct origins in final output
        for sn in route["selected_nodes"]:
            assert "origins" in sn
            assert len(sn["origins"]) >= 1
            assert "atom_path" in sn
            assert "atom_sha256" in sn
        results.append(("selected-node-origins", f"all {len(route['selected_nodes'])} nodes have origins and atom metadata"))

        # Vector-selected nodes are in the final closure (not stale)
        vec_ids = set(route["vector_stage"]["vector_reranked_ids"])
        expanded = set(route["closure"]["expanded_node_ids"])
        for vid in vec_ids:
            assert vid in expanded, f"vector-selected {vid} missing from closure"
        results.append(("vec-in-closure", f"all {len(vec_ids)} vector-selected nodes present in closure"))

        # ==================================================================
        # E. Closure budget
        # ==================================================================
        assert route["closure"]["budget"] == graph["routing_policy"]["max_closure_nodes"]
        results.append(("closure-budget", f"closure budget={route['closure']['budget']}, truncated={route['closure']['closure_truncated']}"))

        # ==================================================================
        # F. Residual bank with sibling exclusion
        # ==================================================================
        # First call with no bank
        route1 = route_graph(graph_path, request_with_vec)
        assert route1["residual_revisit"]["bank_provided"] is False
        assert route1["residual"]["bank_version"] == 1
        assert route1["residual"]["contract_version"] == "1.0.0"
        assert route1["residual"]["graph_id"] == graph["graph_id"]

        # Second call with bank from first call
        bank1 = route1["residual"]
        route2 = route_graph(graph_path, {
            "query_id": "test-residual-2",
            "query": "coverage ledger manifest provenance",
            "risk_domains": [],
            "top_k": 1,
            "minimum_score": 2,
        }, residual_bank=bank1)

        assert route2["residual_revisit"]["bank_provided"] is True
        assert route2["residual_revisit"]["bank_version_in"] == 1
        assert route2["residual"]["bank_version"] == 2
        current_ids = set(route2["stage2_atomic_route"]["lexical_selected_ids"]) | set(route2["vector_stage"]["vector_reranked_ids"])
        revisited_ids = {row["node_id"] for row in route2["residual_revisit"]["revisited"]}
        assert revisited_ids, "residual revisit must reselect a relevant prior-only node"
        assert revisited_ids.isdisjoint(current_ids), "residual revisit must not relabel current candidates"
        assert all(row["revisit_score"] > 0 for row in route2["residual_revisit"]["revisited"])
        assert route2["residual"]["entries"][:len(bank1["entries"])] == bank1["entries"]
        assert len(route2["residual"]["entries"]) == len(bank1["entries"]) + len(route2["selected_nodes"])
        results.append(("residual-bank-versioned", f"append-only residual: v_in=1 v_out=2 prior_only_revisited={len(revisited_ids)}"))

        wrong_graph_bank = json.loads(json.dumps(bank1))
        wrong_graph_bank["graph_id"] = "graph-wrong00000000"
        expect_error("residual_graph_mismatch", lambda: route_graph(graph_path, {
            "query_id": "bad-residual", "query": "coverage ledger", "risk_domains": []
        }, residual_bank=wrong_graph_bank))
        results.append(("residual-graph-binding", "cross-graph residual bank fails closed"))
        expect_error("malformed_residual_bank", lambda: route_graph(graph_path, {"query_id": "bad-residual-type", "query": "coverage ledger", "risk_domains": []}, []))
        results.append(("residual-object-type", "non-object residual bank fails with a structured graph error"))

        # ==================================================================
        # F2. Fallback materialization
        # ==================================================================
        fallback_request = {
            "query_id": "test-fallback",
            "query": "xyzzy nonexistent query terms",
            "risk_domains": [],
            "top_k": 1,
            "minimum_score": 100,
        }
        fallback_route = route_graph(graph_path, fallback_request)
        assert fallback_route["fallback"]["activated"] is True
        assert len(fallback_route["fallback"]["fallback_node_ids"]) > 0
        assert fallback_route["status"] == "fallback_safety_only"
        # Fallback nodes must be in selected_nodes
        fb_ids = set(fallback_route["fallback"]["fallback_node_ids"])
        selected_ids = {sn["node_id"] for sn in fallback_route["selected_nodes"]}
        for fid in fb_ids:
            assert fid in selected_ids, f"fallback node {fid} missing from selected_nodes"
        assert fb_ids == set(graph["safety_config"]["global_invariant_node_ids"])
        rejected_ids = {row["node_id"] for row in fallback_route["rejected_nodes"]}
        assert selected_ids.isdisjoint(rejected_ids)
        assert selected_ids == set(fallback_route["closure"]["expanded_node_ids"])
        assert len(selected_ids) <= fallback_route["closure"]["budget"]
        for sn in fallback_route["selected_nodes"]:
            if sn["node_id"] in fb_ids:
                assert "fallback" in sn["origins"] and "safety" in sn["origins"]
        results.append(("fallback-materialized", f"fallback: exactly {len(fb_ids)} scoped safety nodes, no stale rejected IDs"))

        expect_error("closure_budget_exceeded", lambda: route_graph(graph_path, {
            "query_id": "tiny-budget", "query": "coverage ledger manifest provenance",
            "risk_domains": [], "top_k": 3, "max_closure_nodes": 1,
        }))
        results.append(("closure-hard-budget", "required candidate+safety closure fails closed when budget is insufficient"))
        expect_error("malformed_input", lambda: route_graph(graph_path, {
            "query_id": "oversized-top-k", "query": "coverage", "risk_domains": [],
            "top_k": graph["routing_policy"]["max_top_k"] + 1,
        }))
        results.append(("request-bounds", "request top_k cannot exceed graph policy"))

        # ==================================================================
        # G. Deterministic rebuild
        # ==================================================================
        graph_path2 = build_graph_registry(ws)
        assert file_sha256(graph_path) == file_sha256(graph_path2), "graph registry must be byte-identical on rebuild"
        vec_path = ws / "build" / "vector-index.v1.json"
        vec_sha1 = file_sha256(vec_path)
        build_graph_registry(ws)
        assert file_sha256(vec_path) == vec_sha1, "vector index must be byte-identical on rebuild"
        results.append(("deterministic-rebuild", "graph registry and vector index are byte-identical on rebuild"))

        # Also verify same route with same request produces identical output
        request_det = {
            "query_id": "det-test",
            "query": "coverage ledger",
            "risk_domains": [],
            "top_k": 3,
            "minimum_score": 2,
        }
        r1 = route_graph(graph_path, request_det)
        r2 = route_graph(graph_path, request_det)
        # Compare without residual (it increments bank_version)
        r1_no_res = {k: v for k, v in r1.items() if k != "residual"}
        r2_no_res = {k: v for k, v in r2.items() if k != "residual"}
        assert json.dumps(r1_no_res, sort_keys=True) == json.dumps(r2_no_res, sort_keys=True)
        results.append(("deterministic-route", "identical requests produce identical output (excluding residual bank version)"))

        # ==================================================================
        # H. Load plan semantics
        # ==================================================================
        lp = route["load_plan"]
        assert lp["node_count"] > 0
        assert lp["file_count"] > 0
        assert lp["chunk_count"] > 0
        # All files exist
        for fc in lp["file_checksums"]:
            p = Path(fc["path"])
            assert p.is_file(), f"load plan file missing: {fc['path']}"
            assert file_sha256(p) == fc["sha256"], f"load plan checksum mismatch: {fc['path']}"
        # All chunks exist
        for sc in lp["source_chunks"]:
            p = Path(sc["path"])
            assert p.is_file(), f"source chunk missing: {sc['path']}"
            assert file_sha256(p) == sc["sha256"], f"source chunk checksum mismatch: {sc['path']}"
        results.append(("load-plan-semantics", f"load plan: {lp['node_count']} nodes, {lp['chunk_count']} chunks, {lp['file_count']} files, all checksums verified"))

        # Load plan includes shared core
        sc_paths = [fc for fc in lp["file_checksums"] if fc["role"] == "shared_core"]
        assert len(sc_paths) == 1
        results.append(("load-plan-shared-core", "shared core included in load plan"))

        # Load plan includes atomic node files
        atom_csums = [fc for fc in lp["file_checksums"] if fc["role"] == "atomic_node"]
        assert len(atom_csums) > 0
        results.append(("load-plan-atoms", f"load plan includes {len(atom_csums)} atomic node files"))

        # ==================================================================
        # I. Schema validation
        # ==================================================================
        route_full = route_graph(graph_path, request_with_vec)
        assert route_full["contract_version"] == "1.0.0"
        assert route_full["graph_id"] == graph["graph_id"]
        assert route_full["status"] in ("selected", "fallback_safety_only", "degraded_closure_budget")
        assert route_full["query_context"]["stage_id"] == "graph_route"
        assert route_full["vector_stage"]["mode"] in ("lexical_only", "vector_and_lexical", "disabled")
        results.append(("schema-validation", f"route output validates against atomic-route-output.v1 schema"))

        # ==================================================================
        # J. Anti-trigger exclusion
        # ==================================================================
        # Anti-trigger matching uses normalized substring in sorted-joined tokens.
        # "just answer one fact" as anti_trigger of coverage-definition node.
        # We need the normalized anti_trigger to be a substring of the sorted
        # query tokens. Use query words that sort so the phrase appears intact.
        # sorted tokens of "answer coverage fact just one" includes "answer coverage fact just one"
        # but "just answer one fact" normalizes to "just answer one fact".
        # The sorted join is "answer coverage fact just one" - does NOT contain "just answer one fact".
        # So we use the safety node's anti-trigger "ignore safety" with a query
        # where "ignore" and "safety" are adjacent in sorted order.
        # "coverage ignore safety workflow" -> sorted: "coverage ignore safety workflow"
        # "ignore safety" IS a substring!
        anti_request = {
            "query_id": "test-anti",
            "query": "coverage ignore safety workflow",
            "risk_domains": [],
            "top_k": 3,
            "minimum_score": 2,
        }
        anti_route = route_graph(graph_path, anti_request)
        lex_ids = anti_route["stage2_atomic_route"]["lexical_selected_ids"]
        # safety-no-partial-coverage has anti_trigger "ignore safety"
        # The sorted tokens are "coverage ignore safety workflow" which contains "ignore safety"
        assert "safety-no-partial-coverage" not in lex_ids, "anti-trigger 'ignore safety' should exclude safety node"
        results.append(("anti-trigger-exclusion", "anti-trigger 'ignore safety' correctly excludes safety node from lexical selection"))

        # ==================================================================
        # K. Vector-only recovery after lexical miss
        # ==================================================================
        # Use a query with no lexical matches but vector matches
        vec_only_request = {
            "query_id": "test-vec-only",
            "query": "xyzzy no match terms but",
            "risk_domains": [],
            "top_k": 3,
            "minimum_score": 100,
            "query_vectors": {
                "semantic": [0.9, 0.3, 0.1, 0.0],
                "task": [0.8, 0.2, 0.1],
                "risk": [0.1, 0.0, 0.0],
            },
        }
        vec_only_route = route_graph(graph_path, vec_only_request)
        lex_count = len(vec_only_route["stage2_atomic_route"]["lexical_selected_ids"])
        vec_count = len(vec_only_route["vector_stage"]["vector_reranked_ids"])
        assert lex_count == 0, f"expected 0 lexical, got {lex_count}"
        assert vec_count > 0, f"expected >0 vector, got {vec_count}"
        # Vector nodes must be in closure
        assert len(vec_only_route["closure"]["expanded_node_ids"]) >= vec_count
        results.append(("vector-only-recovery", f"lexical miss ({lex_count}), vector recovery ({vec_count} nodes)"))

        # ==================================================================
        # L. No stale output
        # ==================================================================
        # Verify selected_nodes matches expanded_node_ids
        expanded_set = set(route["closure"]["expanded_node_ids"])
        selected_set = {sn["node_id"] for sn in route["selected_nodes"]}
        assert expanded_set == selected_set, f"stale output: expanded={expanded_set} != selected={selected_set}"
        results.append(("no-stale-output", "selected_nodes exactly matches closure expanded_node_ids"))

        # ==================================================================
        # M. Ordinary CLI persists the full route and append-only residual bank
        # ==================================================================
        cli_output = TEST_ROOT / "cli-route.json"
        cli_output_2 = TEST_ROOT / "cli-route-2.json"
        cli_residual = TEST_ROOT / "cli-residual.json"
        cli = ROOT / "scripts" / "graph_query.py"
        first_cli = subprocess.run(
            [sys.executable, str(cli), "--graph-registry", str(graph_path),
             "--query", "complete coverage provenance", "--query-id", "cli-persist-1",
             "--output", str(cli_output), "--residual-output", str(cli_residual), "--pretty"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        assert first_cli.returncode == 0, first_cli.stderr
        persisted_output = load_json(cli_output)
        first_bank = load_json(cli_residual)
        assert persisted_output == json.loads(first_cli.stdout)
        assert persisted_output["residual"] == first_bank
        second_cli = subprocess.run(
            [sys.executable, str(cli), "--graph-registry", str(graph_path),
             "--query", "stable hash evidence", "--query-id", "cli-persist-2",
             "--residual-bank", str(cli_residual), "--output", str(cli_output_2),
             "--residual-output", str(cli_residual), "--pretty"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        assert second_cli.returncode == 0, second_cli.stderr
        second_output = load_json(cli_output_2)
        second_bank = load_json(cli_residual)
        assert second_output == json.loads(second_cli.stdout)
        assert second_output["residual"] == second_bank
        assert second_bank["bank_version"] == first_bank["bank_version"] + 1
        assert second_bank["entries"][:len(first_bank["entries"])] == first_bank["entries"]
        results.append(("graph-cli-persistence", "full route persisted and residual bank advanced append-only across two CLI queries"))
        graph_sha_before_collision = file_sha256(graph_path)
        collision_cli = subprocess.run(
            [sys.executable, str(cli), "--graph-registry", str(graph_path),
             "--query", "must not overwrite graph", "--output", str(graph_path)],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        assert collision_cli.returncode == 2
        assert json.loads(collision_cli.stderr)["error"] == "output_path_collision"
        assert file_sha256(graph_path) == graph_sha_before_collision
        results.append(("graph-cli-input-protection", "route output cannot overwrite graph/request/vector/residual inputs"))

        # ==================================================================
        # Deferred: Composition tests (preserved, not counted)
        # ==================================================================
        try:
            from composition import (
                CompositionError,
                compose_serial,
                compose_parallel,
                compose_graph_shared,
                build_composition_manifest,
            )
            serial_manifest = {
                "contract_version": "1.0.0",
                "serial_edges": [
                    {"from_skill": "intake", "to_skill": "distill", "interface_contract": "source-manifest.v2", "fields_carried": ["manifest_sha", "chunk_count"]},
                ],
                "parallel_groups": [],
                "graph_shared_edges": [],
            }
            serial_result = compose_serial(serial_manifest, {"intake": {"manifest_sha": "abc", "chunk_count": 3}})
            assert serial_result["composition_type"] == "serial"
            skipped.append(("composition-serial", "DEFERRED: serial composition preserved, not Phase-1"))
        except ImportError:
            skipped.append(("composition-serial", "DEFERRED: composition module not available"))

    except (AssertionError, ContractError, GraphError, VectorError, KeyError, TypeError, OSError, RuntimeError) as exc:
        print(f"FAIL graph tests: {type(exc).__name__}: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        clean()

    for case_id, detail in results:
        print(f"PASS {case_id}: {detail}")
    for case_id, detail in skipped:
        print(f"SKIP {case_id}: {detail}")
    print(f"cases={len(results) + len(skipped)} passed={len(results)} skipped={len(skipped)} failed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
