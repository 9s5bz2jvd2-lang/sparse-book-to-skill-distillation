#!/usr/bin/env python3
"""Prepare or evaluate an authorized external real-material sparse-reading trial.

This harness never supplies semantic artifacts or query gold. Those inputs must be
source-grounded and human/agent authored. Reports omit source/query bodies and
separate deterministic structural measurements from authored semantic evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from contract_validation import CONTRACT_VERSION, ContractError, load_json, validate_instance
from pipeline import (
    ROOT,
    build_registry,
    finalize_queue_and_source_map,
    install_authored_artifacts,
    intake_sources,
    prepare_distillation,
    query_registry,
    validate_distillation,
    write_json,
)


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def evaluate_workspace(workspace: Path, gold_path: Path, report_path: Path, authored: Path | None = None) -> tuple[dict[str, Any], bool]:
    workspace = workspace.resolve()
    failures: list[dict[str, str]] = []
    if authored is not None:
        install_authored_artifacts(workspace, authored)
    finalize_queue_and_source_map(workspace)
    validated = validate_distillation(workspace)
    registry_path, _, registry = build_registry(workspace)
    gold = load_json(gold_path)
    validate_instance(gold, load_json(ROOT / "contracts" / "query-gold.v2.schema.json"))
    case_ids = [case["case_id"] for case in gold["cases"]]
    if len(case_ids) != len(set(case_ids)):
        raise ContractError("duplicate_gold_case", "query gold case_id values must be unique")
    query_ids = [case["request"]["query_id"] for case in gold["cases"]]
    if len(query_ids) != len(set(query_ids)):
        raise ContractError("duplicate_gold_case", "query gold query_id values must be unique")

    query_results: list[dict[str, Any]] = []
    expected_expert_total = 0
    expert_hit_total = 0
    expected_chunk_total = 0
    chunk_hit_total = 0
    status_matches = 0
    exact_route_matches = 0
    exact_source_load_matches = 0
    human_score_rows: list[dict[str, int]] = []
    for case in gold["cases"]:
        case_id = case["case_id"]
        try:
            output = query_registry(registry_path, case["request"])
        except ContractError as exc:
            failures.append({"case_id": case_id, "kind": "query_error", "code": exc.code})
            query_results.append({"case_id": case_id, "status": "error", "error_code": exc.code})
            continue
        actual_experts = output["selected_experts"]
        expected_experts = case["expected_expert_ids"]
        actual_chunks = [item["chunk_id"] for item in output["load_plan"]["source_chunks"]]
        expected_chunks = case["expected_source_chunk_ids"]
        expert_hits = len(set(actual_experts) & set(expected_experts))
        chunk_hits = len(set(actual_chunks) & set(expected_chunks))
        expected_expert_total += len(expected_experts)
        expert_hit_total += expert_hits
        expected_chunk_total += len(expected_chunks)
        chunk_hit_total += chunk_hits
        status_match = output["status"] == case["expected_status"]
        expert_exact = actual_experts == expected_experts
        chunk_exact = actual_chunks == expected_chunks
        status_matches += int(status_match)
        exact_route_matches += int(status_match and expert_exact)
        exact_source_load_matches += int(chunk_exact)
        if not status_match:
            failures.append({"case_id": case_id, "kind": "status_mismatch", "code": "gold_mismatch"})
        if not expert_exact:
            failures.append({"case_id": case_id, "kind": "expert_route_mismatch", "code": "gold_mismatch"})
        if not chunk_exact:
            failures.append({"case_id": case_id, "kind": "source_load_mismatch", "code": "gold_mismatch"})
        query_results.append({
            "case_id": case_id,
            "status": output["status"],
            "status_match": status_match,
            "expected_expert_count": len(expected_experts),
            "selected_expert_count": len(actual_experts),
            "expert_recall": _safe_ratio(expert_hits, len(expected_experts)),
            "expert_exact_match": expert_exact,
            "expected_source_chunk_count": len(expected_chunks),
            "loaded_source_chunk_count": len(actual_chunks),
            "source_chunk_recall": _safe_ratio(chunk_hits, len(expected_chunks)),
            "source_load_exact_match": chunk_exact,
            "load_hashes_verified": True,
            "baseline_sweep_activated": output["safety_sweep"]["activated"],
        })
        if "human_scores" in case:
            scores = case["human_scores"]
            human_score_rows.append({
                "route_relevance": scores["route_relevance"],
                "sparse_context_sufficiency": scores["sparse_context_sufficiency"],
                "source_grounding": scores["source_grounding"],
            })

    manifest = validated["manifest"]
    queue = validated["queue"]
    records = validated["records"]
    completed = sum(record["processing_status"] == "complete" for record in records)
    no_reusable = sum(record["processing_status"] == "complete_no_reusable_knowledge" for record in records)
    human_averages: dict[str, float] = {}
    if human_score_rows:
        for dimension in ("route_relevance", "sparse_context_sufficiency", "source_grounding"):
            human_averages[dimension] = round(sum(row[dimension] for row in human_score_rows) / len(human_score_rows), 3)
    report = {
        "contract_version": CONTRACT_VERSION,
        "report_type": "real_material_readiness_trial",
        "claims_boundary": "Structural metrics are deterministic; route gold and human scores are externally authored evidence, not automated semantic-quality proof.",
        "structural_evidence": {
            "source_count": len(manifest["sources"]),
            "chunk_count": len(manifest["chunks"]),
            "queue_item_count": len(queue["items"]),
            "complete_record_count": completed,
            "no_reusable_record_count": no_reusable,
            "reviewed_chunk_count": len(validated["semantic_review"]["reviewed_chunk_ids"]),
            "coverage_fraction": _safe_ratio(len(records), len(manifest["chunks"])),
            "expert_count": len(registry["experts"]),
            "query_case_count": len(gold["cases"]),
            "query_success_count": len(gold["cases"]) - sum(item["kind"] == "query_error" for item in failures),
            "status_accuracy": _safe_ratio(status_matches, len(gold["cases"])),
            "exact_route_accuracy": _safe_ratio(exact_route_matches, len(gold["cases"])),
            "route_recall_micro": _safe_ratio(expert_hit_total, expected_expert_total),
            "source_load_recall_micro": _safe_ratio(chunk_hit_total, expected_chunk_total),
            "source_load_exact_accuracy": _safe_ratio(exact_source_load_matches, len(gold["cases"])),
        },
        "authored_semantic_evidence": {
            "semantic_review_contract_complete": True,
            "query_gold_authorship": gold["authorship"],
            "gold_case_count": len(gold["cases"]),
            "human_scored_case_count": len(human_score_rows),
            "human_score_scale": "1-5, externally authored; absent scores are not inferred",
            "human_score_averages": human_averages,
            "semantic_quality_automatically_scored": False,
        },
        "query_results": query_results,
        "failures": failures,
    }
    validate_instance(report, load_json(ROOT / "contracts" / "trial-report.v2.schema.json"))
    write_json(report_path, report)
    return report, not failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare", help="intake external authorized source and create review state/templates")
    prepare_parser.add_argument("--source", required=True, type=Path)
    prepare_parser.add_argument("--workspace", required=True, type=Path)
    prepare_parser.add_argument("--chunk-lines", type=int, default=80)
    prepare_parser.add_argument("--allow-pdftotext", action="store_true")
    evaluate_parser = subparsers.add_parser("evaluate", help="validate authored artifacts and evaluate external query gold")
    evaluate_parser.add_argument("--workspace", required=True, type=Path)
    evaluate_parser.add_argument("--query-gold", required=True, type=Path)
    evaluate_parser.add_argument("--report", required=True, type=Path)
    evaluate_parser.add_argument("--authored", type=Path, help="optional external records/l3/shared-core/semantic-review bundle")
    run_parser = subparsers.add_parser("run", help="fresh intake + external authored bundle + evaluation")
    run_parser.add_argument("--source", required=True, type=Path)
    run_parser.add_argument("--authored", required=True, type=Path)
    run_parser.add_argument("--query-gold", required=True, type=Path)
    run_parser.add_argument("--workspace", required=True, type=Path)
    run_parser.add_argument("--report", required=True, type=Path)
    run_parser.add_argument("--chunk-lines", type=int, default=80)
    run_parser.add_argument("--allow-pdftotext", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            manifest = intake_sources(args.source, args.workspace, max_lines_per_chunk=args.chunk_lines, allow_pdftotext=args.allow_pdftotext)
            prepared = prepare_distillation(args.workspace)
            result: dict[str, Any] = {"status": "prepared_for_authored_review", "manifest_id": manifest["manifest_id"], **prepared}
            success = True
        else:
            if args.command == "run":
                intake_sources(args.source, args.workspace, max_lines_per_chunk=args.chunk_lines, allow_pdftotext=args.allow_pdftotext)
                prepare_distillation(args.workspace)
                authored = args.authored
            else:
                authored = args.authored
            report, success = evaluate_workspace(args.workspace, args.query_gold, args.report, authored)
            result = {"status": "trial_passed" if success else "trial_completed_with_failures", "report": args.report.as_posix(), "failure_count": len(report["failures"])}
    except ContractError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
