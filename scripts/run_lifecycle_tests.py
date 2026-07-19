#!/usr/bin/env python3
"""Execute structured from-zero lifecycle assertions without model or network calls."""

from __future__ import annotations

import hashlib
import io
import shutil
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from contract_validation import ContractError, load_json, validate_instance
from pipeline import (
    ROOT,
    build_registry,
    finalize_queue_and_source_map,
    install_curated_artifacts,
    intake_sources,
    prepare_distillation,
    query_registry,
    validate_distillation,
    write_json,
)
from run_lifecycle_demo import main as run_lifecycle_demo

FIXTURES = ROOT / "tests" / "fixtures" / "lifecycle-cases.v2.json"
FIXTURE_SCHEMA = ROOT / "contracts" / "lifecycle-fixtures.v2.schema.json"
SOURCE = ROOT / "examples" / "from-zero" / "source"
CURATED = ROOT / "examples" / "from-zero" / "curated"
TEST_ROOT = ROOT / "build" / "lifecycle-tests"


def clean_test_root() -> None:
    resolved = TEST_ROOT.resolve()
    try:
        resolved.relative_to((ROOT / "build").resolve())
    except ValueError as exc:
        raise RuntimeError("refusing to clean outside repository build directory") from exc
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)


def setup_workspace(name: str, *, complete: bool) -> Path:
    workspace = TEST_ROOT / name
    intake_sources(SOURCE, workspace, max_lines_per_chunk=6)
    prepare_distillation(workspace)
    if complete:
        install_curated_artifacts(workspace, CURATED)
        finalize_queue_and_source_map(workspace)
    return workspace


def expect_error(code: str, operation: Any) -> None:
    try:
        operation()
    except ContractError as exc:
        if exc.code != code:
            raise AssertionError(f"expected error {code!r}, got {exc.code!r}: {exc.message}") from exc
    else:
        raise AssertionError(f"expected error {code!r}, operation succeeded")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_baseline_sweep(output: dict[str, Any]) -> None:
    sweep = output["safety_sweep"]
    assert sweep["activated"] is True
    assert sweep["phase"] == "post_route"
    assert sweep["baseline_checks"]


def main() -> int:
    fixtures = load_json(FIXTURES)
    validate_instance(fixtures, load_json(FIXTURE_SCHEMA))
    cases = {case["category"]: case for case in fixtures["cases"]}
    if len(cases) != len(fixtures["cases"]):
        print("FAIL lifecycle tests: duplicate fixture category", file=sys.stderr)
        return 1
    results: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []
    clean_test_root()
    TEST_ROOT.mkdir(parents=True)
    try:
        intake_workspace = setup_workspace("intake", complete=False)
        manifest = load_json(intake_workspace / "source-manifest.json")
        queue = load_json(intake_workspace / "work-queue.json")
        expected = cases["intake"]["expected"]
        assert len(manifest["sources"]) == expected["sources"]
        assert len(manifest["chunks"]) == expected["chunks"]
        assert manifest["full_text_status"] == expected["full_text_status"]
        assert {item["status"] for item in queue["items"]} == {expected["all_queue_status"]}
        assert {item["chunk_id"] for item in queue["items"]} == {chunk["chunk_id"] for chunk in manifest["chunks"]}
        for source in manifest["sources"]:
            original_path = intake_workspace / source["original_path"]
            text_path = intake_workspace / source["text_path"]
            assert original_path.is_file() and file_sha256(original_path) == source["source_sha256"]
            assert text_path.is_file() and file_sha256(text_path) == source["text_sha256"]
            source_chunks = [chunk for chunk in manifest["chunks"] if chunk["source_id"] == source["source_id"]]
            source_chunks.sort(key=lambda chunk: chunk["start_line"])
            assert [chunk["chunk_id"] for chunk in source_chunks] == source["chunk_ids"]
            assert b"".join((intake_workspace / chunk["path"]).read_bytes() for chunk in source_chunks) == text_path.read_bytes()
            assert all(file_sha256(intake_workspace / chunk["path"]) == chunk["sha256"] for chunk in source_chunks)
        results.append((cases["intake"]["case_id"], "original/text/chunk hashes, gap-free bytes, queue, and full_text_status"))

        # A failed prior write is an explicit recovery stop, not a silently
        # skipped template.  The corrupt bytes remain for diagnosis and can be
        # replaced only by an operator-controlled clean workspace.
        resume_workspace = setup_workspace("prepare-corrupt-resume", complete=False)
        resume_record = sorted((resume_workspace / "distilled" / "records").glob("*.json"))[0]
        resume_record.write_text("{\n", encoding="utf-8")
        expect_error("existing_artifact_invalid", lambda: prepare_distillation(resume_workspace))
        assert resume_record.read_text(encoding="utf-8") == "{\n"
        results.append(("prepare-corrupt-resume", "corrupt existing template fails closed without overwrite"))

        # Schema-valid bytes are still unsafe to resume when their source/line
        # provenance belongs to a different chunk identity.
        identity_workspace = setup_workspace("prepare-identity-mismatch-resume", complete=False)
        identity_record = sorted((identity_workspace / "distilled" / "records").glob("*.json"))[0]
        identity_payload = load_json(identity_record)
        identity_payload["chunk_provenance"]["source_id"] = "src-mismatched-resume"
        write_json(identity_record, identity_payload)
        identity_bytes = identity_record.read_bytes()
        expect_error("existing_artifact_invalid", lambda: prepare_distillation(identity_workspace))
        assert identity_record.read_bytes() == identity_bytes
        results.append(("prepare-identity-mismatch-resume", "schema-valid provenance mismatch fails closed without overwrite"))

        source_symlink_case = cases["source_symlink"]
        source_symlink = TEST_ROOT / "source-root-link"
        try:
            source_symlink.symlink_to(SOURCE, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            skipped.append((source_symlink_case["case_id"], f"symlink creation unavailable: {type(exc).__name__}"))
        else:
            expect_error(
                source_symlink_case["expected"]["error"],
                lambda: intake_sources(source_symlink, TEST_ROOT / "source-symlink-denied", max_lines_per_chunk=6),
            )
            results.append((source_symlink_case["case_id"], "caller-supplied source-root symlink rejected before resolution"))

        expected_error = cases["unprocessed_chunk"]["expected"]["error"]
        expect_error(expected_error, lambda: validate_distillation(intake_workspace))
        results.append((cases["unprocessed_chunk"]["case_id"], "pending chunk blocked completeness"))

        missing_chunk_workspace = setup_workspace("missing-chunk", complete=True)
        missing_chunk_manifest = load_json(missing_chunk_workspace / "source-manifest.json")
        (missing_chunk_workspace / missing_chunk_manifest["chunks"][0]["path"]).unlink()
        expect_error(cases["missing_chunk"]["expected"]["error"], lambda: validate_distillation(missing_chunk_workspace))
        results.append((cases["missing_chunk"]["case_id"], "missing manifest chunk rejected"))

        bad_artifact_hash_workspace = setup_workspace("bad-artifact-hash", complete=True)
        bad_artifact_path = sorted((bad_artifact_hash_workspace / "distilled" / "records").glob("*.json"))[0]
        bad_artifact = load_json(bad_artifact_path)
        bad_artifact["chunk_sha256"] = "0" * 64
        write_json(bad_artifact_path, bad_artifact)
        expect_error(cases["bad_artifact_hash"]["expected"]["error"], lambda: validate_distillation(bad_artifact_hash_workspace))
        results.append((cases["bad_artifact_hash"]["case_id"], "bad per-chunk artifact hash rejected"))

        bad_hash_workspace = setup_workspace("bad-source-hash", complete=True)
        bad_hash_manifest = load_json(bad_hash_workspace / "source-manifest.json")
        imported_original = bad_hash_workspace / bad_hash_manifest["sources"][0]["original_path"]
        imported_original.write_bytes(imported_original.read_bytes() + b"\nchanged")
        expect_error(cases["bad_source_hash"]["expected"]["error"], lambda: validate_distillation(bad_hash_workspace))
        results.append((cases["bad_source_hash"]["case_id"], "changed imported original bytes rejected"))

        bad_provenance_workspace = setup_workspace("bad-provenance", complete=True)
        first_artifact = sorted((bad_provenance_workspace / "distilled" / "records").glob("*.json"))[0]
        bad_record = load_json(first_artifact)
        bad_record["knowledge_nodes"][0]["provenance"][0]["end_line"] = 999
        write_json(first_artifact, bad_record)
        expect_error(cases["bad_provenance"]["expected"]["error"], lambda: validate_distillation(bad_provenance_workspace))
        results.append((cases["bad_provenance"]["case_id"], "out-of-chunk source locator rejected"))

        wrong_source_workspace = setup_workspace("wrong-provenance-source", complete=True)
        wrong_source_path = sorted((wrong_source_workspace / "distilled" / "records").glob("*.json"))[0]
        wrong_source_record = load_json(wrong_source_path)
        wrong_source_record["knowledge_nodes"][0]["provenance"][0]["source_id"] = "src-0000000000000000"
        write_json(wrong_source_path, wrong_source_record)
        expect_error(cases["bad_provenance_source"]["expected"]["error"], lambda: validate_distillation(wrong_source_workspace))
        results.append((cases["bad_provenance_source"]["case_id"], "chunk/source provenance mismatch rejected"))

        missing_l3_workspace = setup_workspace("missing-l3", complete=True)
        missing_record = load_json(sorted((missing_l3_workspace / "distilled" / "records").glob("*.json"))[0])
        (missing_l3_workspace / missing_record["knowledge_nodes"][0]["l3"]["path"]).unlink()
        expect_error(cases["missing_l3"]["expected"]["error"], lambda: validate_distillation(missing_l3_workspace))
        results.append((cases["missing_l3"]["case_id"], "required L3 absence rejected"))

        unvalidated_workspace = setup_workspace("build-unvalidated", complete=False)
        expect_error(cases["build_refuses_unvalidated"]["expected"]["error"], lambda: build_registry(unvalidated_workspace))
        results.append((cases["build_refuses_unvalidated"]["case_id"], "build reran validation and refused pending input"))

        main_workspace = setup_workspace("complete", complete=True)
        validated = validate_distillation(main_workspace)
        assert validated["node_count"] == 4
        registry_path, index_path, registry = build_registry(main_workspace)
        expected = cases["build"]["expected"]
        assert len(registry["experts"]) == expected["experts"]
        assert [expert["expert_id"] for expert in registry["experts"]] == expected["expert_ids"]
        assert registry["source_manifest_sha256"] == validated["manifest_sha256"]
        assert index_path.is_file() is expected["index_exists"]
        results.append((cases["build"]["case_id"], "complete source-to-validated-registry/index lifecycle"))

        sparse_case = cases["sparse_query"]
        sparse = query_registry(registry_path, sparse_case["request"])
        expected = sparse_case["expected"]
        assert sparse["status"] == expected["status"]
        assert sparse["selected_experts"] == expected["selected_experts"]
        assert sparse["safety_sweep"]["activated"] is expected["sweep_activated"]
        assert_baseline_sweep(sparse)
        expected_shared = (main_workspace / "distilled" / "shared-core.md").resolve().as_posix()
        expected_module = (main_workspace / expected["module_relative"]).resolve().as_posix()
        assert sparse["load_plan"]["files_to_load"] == [expected_shared, expected_module]
        assert sparse["load_plan"]["expert_module_files"] == [expected_module]
        assert [item["path"] for item in sparse["load_plan"]["file_checksums"]] == [expected_shared, expected_module]
        assert all(Path(item["path"]).is_file() and file_sha256(Path(item["path"])) == item["sha256"] for item in sparse["load_plan"]["file_checksums"])
        assert len(sparse["load_plan"]["source_chunks"]) == 1
        planned_chunk = sparse["load_plan"]["source_chunks"][0]
        assert planned_chunk["chunk_id"] == expected["source_chunk_id"]
        assert planned_chunk["start_line"] == expected["source_start_line"]
        assert planned_chunk["end_line"] == expected["source_end_line"]
        assert Path(planned_chunk["path"]).is_file()
        assert file_sha256(Path(planned_chunk["path"])) == planned_chunk["sha256"]
        assert sparse["audit_log"][0]["event"] == "query_and_index_validated"
        assert sparse["audit_log"][-1]["event"] == "exact_load_plan_created"
        results.append((sparse_case["case_id"], "positive route emitted exact checksummed files/chunk and audit trace"))

        tie_case = cases["stable_tie"]
        tie = query_registry(registry_path, tie_case["request"])
        expected = tie_case["expected"]
        assert tie["selected_experts"] == expected["selected_experts"]
        assert [item["expert_id"] for item in tie["route_scores"][:2]] == expected["first_two_scored"]
        assert [item["score"] for item in tie["route_scores"][:2]] == [expected["equal_score"], expected["equal_score"]]
        results.append((tie_case["case_id"], "equal scores resolved by stable priority then ID order"))

        top_k_case = cases["top_k"]
        top_k = query_registry(registry_path, top_k_case["request"])
        assert top_k["selected_experts"] == top_k_case["expected"]["selected_experts"]
        assert len(top_k["selected_experts"]) == top_k_case["request"]["top_k"]
        assert_baseline_sweep(top_k)
        results.append((top_k_case["case_id"], "top-k retained two threshold-eligible experts in stable order"))

        anti_case = cases["anti_trigger"]
        anti = query_registry(registry_path, anti_case["request"])
        expected = anti_case["expected"]
        assert anti["status"] == expected["status"]
        assert anti["selected_experts"] == expected["selected_experts"]
        assert anti["safety_sweep"]["activated"] is expected["sweep_activated"]
        assert_baseline_sweep(anti)
        results.append((anti_case["case_id"], "derived global bypass anti-trigger retained baseline sweep"))

        expert_anti_case = cases["expert_anti_trigger"]
        expert_anti = query_registry(registry_path, expert_anti_case["request"])
        expert_score = next(item for item in expert_anti["route_scores"] if item["expert_id"] == expert_anti_case["expected"]["expert_id"])
        assert expert_anti["status"] == expert_anti_case["expected"]["status"]
        assert expert_score["anti_trigger_hits"] == expert_anti_case["expected"]["anti_trigger_hits"]
        assert expert_score["eligible"] is False
        assert_baseline_sweep(expert_anti)
        results.append((expert_anti_case["case_id"], "per-expert anti-trigger made a threshold hit ineligible"))

        reject_case = cases["reject_anti_trigger"]
        rejected = query_registry(registry_path, reject_case["request"])
        assert rejected["status"] == reject_case["expected"]["status"]
        assert rejected["selected_experts"] == []
        assert_baseline_sweep(rejected)
        results.append((reject_case["case_id"], "global reject anti-trigger retained unconditional baseline sweep"))

        below_case = cases["below_threshold"]
        below = query_registry(registry_path, below_case["request"])
        expected = below_case["expected"]
        assert below["status"] == expected["status"]
        assert below["selected_experts"] == expected["selected_experts"]
        assert below["safety_sweep"]["ambiguous"] is expected["ambiguous"]
        assert below["safety_sweep"]["safety_experts_activated"] == expected["safety_experts_activated"]
        assert below["load_plan"]["files_to_load"][0] == expected_shared
        assert_baseline_sweep(below)
        results.append((below_case["case_id"], "no-hit retained shared core, baseline sweep, and ambiguous-route safety"))

        safety_case = cases["safety_sweep"]
        safety = query_registry(registry_path, safety_case["request"])
        expected = safety_case["expected"]
        assert safety["safety_sweep"]["activated"] is expected["sweep_activated"]
        assert safety["safety_sweep"]["high_risk"] is expected["high_risk"]
        assert safety["safety_sweep"]["safety_experts_activated"] == expected["safety_experts_activated"]
        assert expected["hit_contains"] in safety["safety_sweep"]["hits"]
        assert_baseline_sweep(safety)
        safety_module = (main_workspace / expected["safety_module_relative"]).resolve().as_posix()
        assert safety_module in safety["load_plan"]["expert_module_files"]
        results.append((safety_case["case_id"], "high-risk injection indicator triggered mandatory safety module"))

        ambiguous_case = cases["ambiguous_sweep"]
        ambiguous = query_registry(registry_path, ambiguous_case["request"])
        expected = ambiguous_case["expected"]
        assert ambiguous["safety_sweep"]["activated"] is expected["sweep_activated"]
        assert ambiguous["safety_sweep"]["ambiguous"] is expected["ambiguous"]
        assert bool(ambiguous["safety_sweep"]["extra_checks"]) is expected["extra_checks"]
        assert ambiguous["safety_sweep"]["safety_experts_activated"] == expected["safety_experts_activated"]
        assert_baseline_sweep(ambiguous)
        results.append((ambiguous_case["case_id"], "cutoff tie retained baseline and triggered ambiguous-route extra checks/safety"))

        malformed_case = cases["malformed_input"]
        expect_error(malformed_case["expected"]["error"], lambda: query_registry(registry_path, malformed_case["request"]))
        results.append((malformed_case["case_id"], "missing required query field rejected"))

        version_case = cases["schema_mismatch"]
        expect_error(version_case["expected"]["error"], lambda: query_registry(registry_path, version_case["request"]))
        results.append((version_case["case_id"], "unsupported contract version rejected"))

        index_workspace = setup_workspace("bad-index", complete=True)
        bad_index_registry, bad_index_path, _ = build_registry(index_workspace)
        bad_index = load_json(bad_index_path)
        bad_index["experts"][0]["tie_break_priority"] += 1
        write_json(bad_index_path, bad_index)
        index_case = cases["index_mismatch"]
        expect_error(index_case["expected"]["error"], lambda: query_registry(bad_index_registry, index_case["request"]))
        results.append((index_case["case_id"], "schema-valid but registry-inconsistent sparse index rejected"))

        registry_workspace = setup_workspace("changed-registry", complete=True)
        changed_registry_path, _, changed_registry_data = build_registry(registry_workspace)
        changed_registry_data["experts"][0]["title"] += " changed"
        write_json(changed_registry_path, changed_registry_data)
        registry_case = cases["registry_mismatch"]
        expect_error(registry_case["expected"]["error"], lambda: query_registry(changed_registry_path, registry_case["request"]))
        results.append((registry_case["case_id"], "registry build-ID binding rejected schema-valid byte change"))

        changed_l3_workspace = setup_workspace("changed-l3", complete=True)
        changed_l3_registry, _, changed_l3_data = build_registry(changed_l3_workspace)
        changed_l3_path = changed_l3_workspace / changed_l3_data["experts"][0]["l3_files"][0]["path"]
        changed_l3_path.write_bytes(changed_l3_path.read_bytes() + b"\nchanged")
        l3_checksum_case = cases["changed_l3_file"]
        expect_error(l3_checksum_case["expected"]["error"], lambda: query_registry(changed_l3_registry, l3_checksum_case["request"]))
        results.append((l3_checksum_case["case_id"], "post-build L3 checksum change rejected before load"))

        changed_shared_workspace = setup_workspace("changed-shared-core", complete=True)
        changed_shared_registry, _, _ = build_registry(changed_shared_workspace)
        changed_shared_path = changed_shared_workspace / "distilled" / "shared-core.md"
        changed_shared_path.write_bytes(changed_shared_path.read_bytes() + b"\nchanged")
        shared_checksum_case = cases["changed_shared_core"]
        expect_error(shared_checksum_case["expected"]["error"], lambda: query_registry(changed_shared_registry, shared_checksum_case["request"]))
        results.append((shared_checksum_case["case_id"], "post-build shared-core checksum change rejected before load"))

        changed_workspace = setup_workspace("changed-load-file", complete=True)
        changed_registry, _, _ = build_registry(changed_workspace)
        changed_manifest = load_json(changed_workspace / "source-manifest.json")
        selected_chunk = next(item for item in changed_manifest["chunks"] if item["chunk_id"] == "chunk-199c1e4f467e3bd46732")
        selected_chunk_path = changed_workspace / selected_chunk["path"]
        selected_chunk_path.write_bytes(selected_chunk_path.read_bytes() + b"changed")
        changed_case = cases["changed_load_file"]
        expect_error(changed_case["expected"]["error"], lambda: query_registry(changed_registry, changed_case["request"]))
        results.append((changed_case["case_id"], "post-build planned chunk hash change rejected before load"))

        cleanup_case = cases["demo_cleanup"]
        demo_workspace = TEST_ROOT / "demo-cleanup"
        with redirect_stdout(io.StringIO()):
            demo_exit = run_lifecycle_demo(["--workspace", str(demo_workspace)])
        assert demo_exit == cleanup_case["expected"]["exit_code"]
        assert not demo_workspace.exists()
        results.append((cleanup_case["case_id"], "from-zero demo removed its fresh temporary workspace in finally"))
    except (AssertionError, ContractError, KeyError, TypeError, OSError, RuntimeError) as exc:
        print(f"FAIL lifecycle tests: {exc}", file=sys.stderr)
        return 1
    finally:
        clean_test_root()

    executed_case_count = len(results) + len(skipped)
    # The fixture catalog remains the inherited contract inventory; the Luna
    # optimization adds two focused recovery regressions outside that catalog.
    expected_case_count = len(fixtures["cases"]) + 2
    if executed_case_count != expected_case_count:
        print(
            f"FAIL lifecycle tests: expected={expected_case_count} fixtures={len(fixtures['cases'])} executed_or_skipped={executed_case_count}",
            file=sys.stderr,
        )
        return 1
    for case_id, detail in results:
        print(f"PASS {case_id}: {detail}")
    for case_id, detail in skipped:
        print(f"SKIP {case_id}: {detail}")
    print(f"cases={executed_case_count} passed={len(results)} skipped={len(skipped)} failed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
