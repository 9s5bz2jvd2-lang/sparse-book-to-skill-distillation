#!/usr/bin/env python3
"""Generated scale/resume and external-gold harness tests; not real-book semantic proof."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pipeline
from contract_validation import ContractError, load_json
from pipeline import (
    ROOT,
    PipelineError,
    _expected_batch_id,
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


def test_prefix_checkpoint() -> str:
    source = TEST_ROOT / "prefix-source.md"
    lines = [f"## Prefix section {index:04d}\nRedistributable prefix marker {index:04d}.\n" for index in range(60)]
    source.write_text("".join(lines), encoding="utf-8")
    workspace = TEST_ROOT / "prefix-workspace"
    manifest = intake_sources(source, workspace, max_lines_per_chunk=4)
    prepare_distillation(workspace)
    assert len(manifest["chunks"]) == 30
    state_path = workspace / "review-state.json"

    # Fresh workspace state and library default claim size are both 3.
    assert load_json(state_path)["batch_size"] == 3
    default_batch = claim_review_batch(workspace)
    assert len(default_batch["items"]) == 3
    assert load_json(state_path)["batch_size"] == 3

    # A pending head means an empty committable prefix: error, bytes unchanged.
    state_bytes = state_path.read_bytes()
    expect_error("incomplete_review_batch", lambda: checkpoint_review_batch(workspace))
    assert state_path.read_bytes() == state_bytes

    # An entirely valid active slice still commits whole, as before.
    for item in default_batch["items"]:
        mark_no_reusable(workspace, item["artifact_path"])
    progress = checkpoint_review_batch(workspace)
    assert progress["checkpointed"] == 3 and progress["completed_chunks"] == 3

    # Batch size may change only between batches; claim the next 17-item slice.
    batch17 = claim_review_batch(workspace, batch_size=17)
    assert len(batch17["items"]) == 17
    assert load_json(state_path)["batch_size"] == 17

    # 5 of 17 authored: commit exactly 5, leave 12 active with canonical state.
    for item in batch17["items"][:5]:
        mark_no_reusable(workspace, item["artifact_path"])
    progress = checkpoint_review_batch(workspace)
    assert progress["checkpointed"] == 5 and progress["completed_chunks"] == 8
    state = load_json(state_path)
    remaining_ids = [item["chunk_id"] for item in batch17["items"][5:]]
    assert state["active_chunk_ids"] == remaining_ids and len(remaining_ids) == 12
    assert state["active_batch_id"] == _expected_batch_id(remaining_ids, 8)
    assert state["all_chunks_checkpointed"] is False

    # Positions 1,2,4 authored while 3 pending: commit 1-2 only, preserve 4.
    remaining_items = batch17["items"][5:]
    for offset in (0, 1, 3):
        mark_no_reusable(workspace, remaining_items[offset]["artifact_path"])
    progress = checkpoint_review_batch(workspace)
    assert progress["checkpointed"] == 2 and progress["completed_chunks"] == 10
    state = load_json(state_path)
    assert state["active_chunk_ids"][0] == remaining_items[2]["chunk_id"]
    fourth = load_json(workspace / remaining_items[3]["artifact_path"])
    assert fourth["processing_status"] != "pending"

    # Re-running after the pending gap is authored commits the next prefix
    # (including the preserved candidate) without duplicating completed IDs.
    mark_no_reusable(workspace, remaining_items[2]["artifact_path"])
    progress = checkpoint_review_batch(workspace)
    assert progress["checkpointed"] == 2 and progress["completed_chunks"] == 12
    queue = load_json(workspace / "work-queue.json")
    queue_ids = [item["chunk_id"] for item in queue["items"]]
    state = load_json(state_path)
    assert len(set(state["completed_chunk_ids"])) == len(state["completed_chunk_ids"])
    assert state["completed_chunk_ids"] == queue_ids[:12]

    # Nothing newly authored: repeated checkpoint makes no progress, no bytes change.
    state_bytes = state_path.read_bytes()
    expect_error("incomplete_review_batch", lambda: checkpoint_review_batch(workspace))
    assert state_path.read_bytes() == state_bytes

    # Invalid non-pending records inside the authored prefix hard-fail unchanged:
    # identity/hash, provenance, and required content shape.
    head_item = next(item for item in queue["items"] if item["chunk_id"] == state["active_chunk_ids"][0])
    head_path = workspace / head_item["artifact_path"]
    mark_no_reusable(workspace, head_item["artifact_path"])
    pristine_record = load_json(head_path)
    state_bytes = state_path.read_bytes()
    broken = json.loads(json.dumps(pristine_record))
    broken["chunk_sha256"] = "0" * 64
    write_json(head_path, broken)
    expect_error("chunk_artifact_mismatch", lambda: checkpoint_review_batch(workspace))
    assert state_path.read_bytes() == state_bytes
    broken = json.loads(json.dumps(pristine_record))
    broken["chunk_provenance"]["source_id"] = "src-" + "0" * 16
    write_json(head_path, broken)
    expect_error("broken_provenance", lambda: checkpoint_review_batch(workspace))
    assert state_path.read_bytes() == state_bytes
    broken = json.loads(json.dumps(pristine_record))
    broken["processing_status"] = "complete"
    broken["no_reusable_reason"] = ""
    write_json(head_path, broken)
    expect_error("incomplete_review_batch", lambda: checkpoint_review_batch(workspace))
    assert state_path.read_bytes() == state_bytes
    write_json(head_path, pristine_record)

    # An injected persistence failure before the atomic replace leaves the prior
    # state intact; the rerun then succeeds.
    original_write_json = pipeline.write_json

    def failing_write_json(path: Path, value: Any) -> None:
        raise PipelineError("injected_write_failure", f"injected failure before atomic replace: {path.name}")

    pipeline.write_json = failing_write_json
    try:
        expect_error("injected_write_failure", lambda: checkpoint_review_batch(workspace))
    finally:
        pipeline.write_json = original_write_json
    assert state_path.read_bytes() == state_bytes
    progress = checkpoint_review_batch(workspace)
    assert progress["checkpointed"] == 1 and progress["completed_chunks"] == 13

    # The CLI default claim size is 3 on a fresh workspace.
    cli_workspace = TEST_ROOT / "prefix-cli-workspace"
    intake_sources(source, cli_workspace, max_lines_per_chunk=4)
    prepare_distillation(cli_workspace)
    cli = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "review_queue.py"), "next", "--workspace", str(cli_workspace)],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert cli.returncode == 0, cli.stderr
    assert len(json.loads(cli.stdout)["items"]) == 3
    assert load_json(cli_workspace / "review-state.json")["batch_size"] == 3

    # An old workspace whose stored batch size is 20 stays loadable, is never
    # resized while active, and drains through repeated prefix checkpoints.
    old_source = TEST_ROOT / "old-batch-source.md"
    old_source.write_text("".join(lines[:50]), encoding="utf-8")
    old_workspace = TEST_ROOT / "old-batch-workspace"
    old_manifest = intake_sources(old_source, old_workspace, max_lines_per_chunk=4)
    prepare_distillation(old_workspace)
    assert len(old_manifest["chunks"]) == 25
    old_state_path = old_workspace / "review-state.json"
    old_state = load_json(old_state_path)
    old_state["batch_size"] = 20
    write_json(old_state_path, old_state)
    old_batch = claim_review_batch(old_workspace, batch_size=20)
    assert len(old_batch["items"]) == 20
    unresized = claim_review_batch(old_workspace)
    assert unresized == old_batch
    assert load_json(old_state_path)["batch_size"] == 20
    for item in old_batch["items"][:7]:
        mark_no_reusable(old_workspace, item["artifact_path"])
    progress = checkpoint_review_batch(old_workspace)
    assert progress["checkpointed"] == 7 and progress["completed_chunks"] == 7
    while not progress["all_chunks_checkpointed"]:
        batch = claim_review_batch(old_workspace, batch_size=20)
        for item in batch["items"]:
            mark_no_reusable(old_workspace, item["artifact_path"])
        progress = checkpoint_review_batch(old_workspace)
    old_state = load_json(old_state_path)
    assert old_state["all_chunks_checkpointed"] is True
    assert len(old_state["completed_chunk_ids"]) == 25
    return "longest-valid-contiguous-prefix checkpoint committed partial/gapped batches, hard-failed invalid prefix records and injected write faults without state mutation, kept default 3, and drained a stored-20 workspace"


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
        results.append(("prefix-checkpoint-fault-compat", test_prefix_checkpoint()))
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
