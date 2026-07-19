#!/usr/bin/env python3
"""Generated scale/resume and external-gold harness tests; not real-book semantic proof."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from contract_validation import ContractError, load_json
from pipeline import (
    ROOT,
    checkpoint_review_batch,
    claim_review_batch,
    finalize_queue_and_source_map,
    install_curated_artifacts,
    intake_sources,
    prepare_distillation,
    validate_distillation,
    write_json,
)
from real_material_trial import evaluate_workspace

TEST_ROOT = ROOT / "build" / "readiness-tests"
SOURCE = ROOT / "examples" / "from-zero" / "source"
CURATED = ROOT / "examples" / "from-zero" / "curated"


def expect_error(code: str, operation: Any) -> None:
    try:
        operation()
    except ContractError as exc:
        if exc.code != code:
            raise AssertionError(f"expected {code}, got {exc.code}: {exc.message}") from exc
    else:
        raise AssertionError(f"expected {code}, operation succeeded")


def mark_no_reusable(workspace: Path, artifact_relative: str) -> None:
    path = workspace / artifact_relative
    record = load_json(path)
    record["processing_status"] = "complete_no_reusable_knowledge"
    record["chunk_summary"] = "Generated scale fixture chunk; no semantic claim is made."
    record["knowledge_nodes"] = []
    record["no_reusable_reason"] = "Generated redistributable scale fixture used only to exercise structural queue behavior."
    record["uncertainties"] = ["Synthetic structure is not evidence of real-material meaning or quality."]
    write_json(path, record)


def test_scale_resume() -> str:
    source = TEST_ROOT / "generated-source.md"
    workspace = TEST_ROOT / "scale-workspace"
    lines = [f"## Synthetic section {index:04d}\nRedistributable structural marker {index:04d}.\n" for index in range(600)]
    source.write_text("".join(lines), encoding="utf-8")
    manifest = intake_sources(source, workspace, max_lines_per_chunk=4)
    prepare_distillation(workspace)
    assert len(manifest["chunks"]) == 300
    queue = load_json(workspace / "work-queue.json")
    state_path = workspace / "review-state.json"
    pristine_state = load_json(state_path)
    false_state = dict(pristine_state)
    false_state["completed_chunk_ids"] = [item["chunk_id"] for item in queue["items"]]
    false_state["all_chunks_checkpointed"] = True
    write_json(state_path, false_state)
    expect_error("review_state_mismatch", lambda: claim_review_batch(workspace, batch_size=17))
    write_json(state_path, pristine_state)

    first = claim_review_batch(workspace, batch_size=17)
    resumed = claim_review_batch(workspace, batch_size=99)
    assert first == resumed and len(first["items"]) == 17
    expect_error("incomplete_review_batch", lambda: checkpoint_review_batch(workspace))
    for item in first["items"]:
        mark_no_reusable(workspace, item["artifact_path"])
    progress = checkpoint_review_batch(workspace)
    assert progress["completed_chunks"] == 17

    second = claim_review_batch(workspace, batch_size=17)
    queue = load_json(workspace / "work-queue.json")
    future = queue["items"][17 + len(second["items"])]
    mark_no_reusable(workspace, future["artifact_path"])
    expect_error("out_of_order_review", lambda: claim_review_batch(workspace, batch_size=17))
    # Restore the deliberate out-of-order mutation from the pending template.
    record = load_json(workspace / future["artifact_path"])
    record["processing_status"] = "pending"
    record["chunk_summary"] = ""
    record["no_reusable_reason"] = ""
    record["uncertainties"] = []
    write_json(workspace / future["artifact_path"], record)

    while True:
        batch = claim_review_batch(workspace, batch_size=17)
        if batch["all_chunks_checkpointed"]:
            break
        for item in batch["items"]:
            mark_no_reusable(workspace, item["artifact_path"])
        progress = checkpoint_review_batch(workspace)
        if progress["all_chunks_checkpointed"]:
            break
    state = load_json(workspace / "review-state.json")
    assert state["all_chunks_checkpointed"] is True
    assert state["completed_chunk_ids"] == [item["chunk_id"] for item in queue["items"]]
    (workspace / "distilled" / "shared-core.md").write_text(
        "# Synthetic structural fixture\n\nThis file exists only to reach the semantic-review gate in a generated scale test.\n",
        encoding="utf-8",
    )
    finalize_queue_and_source_map(workspace)
    expect_error("semantic_review_incomplete", lambda: validate_distillation(workspace))
    return "300 generated chunks resumed in 17-item contiguous batches; out-of-order work and false semantic completion were rejected"


def test_semantic_review_gate() -> str:
    workspace = TEST_ROOT / "semantic-review-gate"
    intake_sources(SOURCE, workspace, max_lines_per_chunk=6)
    prepare_distillation(workspace)
    install_curated_artifacts(workspace, CURATED)
    finalize_queue_and_source_map(workspace)
    review_path = workspace / "distilled" / "semantic-review.json"
    review = load_json(review_path)
    review["criteria"]["meaning_faithful"] = False
    write_json(review_path, review)
    expect_error("semantic_review_incomplete", lambda: validate_distillation(workspace))
    return "source-grounded semantic review declaration with an unaffirmed criterion blocked validation/build"


def test_trial_harness() -> str:
    workspace = TEST_ROOT / "trial-workspace"
    intake_sources(SOURCE, workspace, max_lines_per_chunk=6)
    prepare_distillation(workspace)
    gold_path = TEST_ROOT / "query-gold.json"
    report_path = TEST_ROOT / "trial-report.json"
    write_json(gold_path, {
        "contract_version": "2.0.0",
        "authorship": "human_or_agent_source_grounded_not_generated_by_router",
        "cases": [{
            "case_id": "coverage-route",
            "request": {
                "contract_version": "2.0.0",
                "query_id": "readiness-gold-001",
                "query": "Create a complete source inventory and coverage ledger with stable chunks.",
                "risk_domains": [],
                "top_k": 1,
            },
            "expected_status": "selected",
            "expected_expert_ids": ["coverage-ledger"],
            "expected_source_chunk_ids": ["chunk-199c1e4f467e3bd46732"],
            "human_scores": {
                "evaluator_label": "synthetic fixture evaluator",
                "route_relevance": 5,
                "sparse_context_sufficiency": 4,
                "source_grounding": 5,
                "notes": "Fixture-only score; not real-material evidence.",
            },
        }],
    })
    report, success = evaluate_workspace(workspace, gold_path, report_path, CURATED)
    assert success is True and not report["failures"]
    assert report["structural_evidence"]["route_recall_micro"] == 1.0
    assert report["structural_evidence"]["source_load_exact_accuracy"] == 1.0
    assert report["authored_semantic_evidence"]["semantic_quality_automatically_scored"] is False
    rendered = report_path.read_text(encoding="utf-8")
    assert "Create a complete source inventory" not in rendered
    assert workspace.resolve().as_posix() not in rendered
    mismatch_gold = load_json(gold_path)
    mismatch_gold["cases"][0]["expected_expert_ids"] = ["semantic-distillation"]
    mismatch_gold["cases"][0]["expected_source_chunk_ids"] = ["chunk-9098d1d1be6b4b5effdd"]
    mismatch_path = TEST_ROOT / "mismatch-gold.json"
    mismatch_report_path = TEST_ROOT / "mismatch-report.json"
    write_json(mismatch_path, mismatch_gold)
    mismatch_report, mismatch_success = evaluate_workspace(workspace, mismatch_path, mismatch_report_path)
    assert mismatch_success is False
    assert {failure["kind"] for failure in mismatch_report["failures"]} == {"expert_route_mismatch", "source_load_mismatch"}
    return "external query gold produced privacy-minimized route/source-load metrics, explicit mismatch failures, and separately labeled human scores"


def main() -> int:
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)
    TEST_ROOT.mkdir(parents=True)
    results: list[tuple[str, str]] = []
    try:
        results.append(("generated-scale-resume", test_scale_resume()))
        results.append(("semantic-review-quality-gate", test_semantic_review_gate()))
        results.append(("real-material-trial-harness", test_trial_harness()))
    except (AssertionError, ContractError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"FAIL readiness tests: {exc}", file=sys.stderr)
        return 1
    finally:
        if TEST_ROOT.exists():
            shutil.rmtree(TEST_ROOT)
    for case_id, detail in results:
        print(f"PASS {case_id}: {detail}")
    print(f"cases={len(results)} passed={len(results)} skipped=0 failed=0")
    print("BOUNDARY generated scale proves structural robustness only; it does not prove real-book semantics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
