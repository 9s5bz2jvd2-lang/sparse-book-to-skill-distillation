#!/usr/bin/env python3
"""Validate repository contracts/templates and execute the real source-to-sparse regression suite."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from check_concept_continuity import main as check_concept_continuity
from check_doc_paths import main as check_doc_paths, markdown_files
from contract_validation import CONTRACT_VERSION, ContractError, load_json, validate_instance
from pipeline import ROOT
from run_lifecycle_tests import FIXTURES, FIXTURE_SCHEMA, main as run_lifecycle_tests
from run_readiness_tests import main as run_readiness_tests


def check_frontmatter() -> None:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    if not skill.startswith("---\n"):
        raise ContractError("invalid_skill", "SKILL.md lacks frontmatter")
    end = skill.find("\n---\n", 4)
    if end < 0:
        raise ContractError("invalid_skill", "SKILL.md frontmatter is not closed")
    frontmatter = skill[4:end]
    for key in ("name:", "description:", "version:"):
        if not any(line.startswith(key) for line in frontmatter.splitlines()):
            raise ContractError("invalid_skill", f"SKILL.md frontmatter lacks {key[:-1]}")
    if "version: 3.0.0" not in frontmatter:
        raise ContractError("invalid_skill", "SKILL.md version must be 3.0.0")


def check_diagram() -> None:
    raw = (ROOT / "assets" / "structure-diagram.mmd").read_text(encoding="utf-8").strip()
    doc = (ROOT / "docs" / "structure-diagram.md").read_text(encoding="utf-8")
    marker = "```mermaid\n"
    if marker not in doc or "\n```" not in doc.split(marker, 1)[1]:
        raise ContractError("invalid_diagram", "docs/structure-diagram.md lacks Mermaid block")
    embedded = doc.split(marker, 1)[1].split("\n```", 1)[0].strip()
    if embedded != raw:
        raise ContractError("invalid_diagram", "canonical and embedded Mermaid diagrams differ")


def check_version_and_license_alignment() -> None:
    active_docs = markdown_files() + [ROOT / "ROUTING.yaml", ROOT / "CHANGELOG.md"]
    # v1 graph schemas are intentional Phase-1 additions; only flag lifecycle v1 stale refs
    stale_markers = ("contract version `1.0.0`", "contract_version: \"1.0.0\"", "examples/worked/")
    for path in sorted(set(active_docs)):
        text = path.read_text(encoding="utf-8")
        for marker in stale_markers:
            if marker in text:
                raise ContractError("stale_contract_reference", f"{path.relative_to(ROOT)} contains stale marker {marker!r}")
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    rules = (ROOT / "RULES.md").read_text(encoding="utf-8")
    required_license_markers = (
        "runyuan noncommercial source-available license 1.0",
        "dario amodei", "noncommercial", "source-available",
        "confirmed on 2026-07-19", "osi-approved", "creative commons",
    )
    stale_license_markers = (
        "cc by-nc 4.0", "creativecommons.org/licenses", "local licensing proposal",
        "owner has not confirmed", "confirmation required before publication",
        "must confirm, replace, or remove", "does not finalize or publish",
    )
    for name, text in (("LICENSE", license_text), ("README.md", readme), ("RULES.md", rules)):
        folded = text.casefold()
        missing = [marker for marker in required_license_markers if marker not in folded]
        if missing:
            raise ContractError("license_alignment", f"{name} lacks custom-license markers: {missing}")
        stale = [marker for marker in stale_license_markers if marker in folded]
        if stale:
            raise ContractError("license_alignment", f"{name} contains contradictory or stale license markers: {stale}")


def main() -> int:
    try:
        schemas = sorted((ROOT / "contracts").glob("*.schema.json"))
        required_v2_schemas = {
            "distilled-chunk.v2.schema.json", "expert-index.v2.schema.json", "expert-registry.v2.schema.json",
            "lifecycle-fixtures.v2.schema.json", "query-gold.v2.schema.json", "query-output.v2.schema.json",
            "query-request.v2.schema.json", "review-state.v2.schema.json", "semantic-review.v2.schema.json",
            "source-manifest.v2.schema.json", "source-map.v2.schema.json", "trial-report.v2.schema.json",
            "work-queue.v2.schema.json",
        }
        graph_v1_schemas = {
            "atomic-node.v1.schema.json", "atom-coverage.v1.schema.json", "atomic-route-output.v1.schema.json",
            "composition-manifest.v1.schema.json", "graph-registry.v1.schema.json", "node-vector.v1.schema.json",
            "residual-bank.v1.schema.json", "vector-index.v1.schema.json",
        }
        required_schemas = required_v2_schemas | graph_v1_schemas
        actual_schemas = {path.name for path in schemas}
        if not required_v2_schemas.issubset(actual_schemas):
            raise ContractError("missing_schema", f"missing v2 lifecycle schemas: {sorted(required_v2_schemas - actual_schemas)}")
        if not graph_v1_schemas.issubset(actual_schemas):
            raise ContractError("missing_schema", f"missing graph v1 schemas: {sorted(graph_v1_schemas - actual_schemas)}")
        for path in schemas:
            schema = load_json(path)
            if not isinstance(schema, dict) or "$id" not in schema:
                raise ContractError("invalid_schema", f"schema lacks $id: {path.name}")
        policy = load_json(ROOT / "contracts" / "routing-policy.v2.json")
        if policy.get("contract_version") != CONTRACT_VERSION:
            raise ContractError("schema_version_mismatch", "routing policy version differs")
        if not policy.get("safety_sweep", {}).get("mandatory"):
            raise ContractError("invalid_policy", "mandatory safety sweep is disabled")

        fixtures = load_json(FIXTURES)
        validate_instance(fixtures, load_json(FIXTURE_SCHEMA))
        record_schema = load_json(ROOT / "contracts" / "distilled-chunk.v2.schema.json")
        curated_records = sorted((ROOT / "examples" / "from-zero" / "curated" / "records").glob("*.json"))
        if len(curated_records) != 3:
            raise ContractError("invalid_demo", "expected exactly three curated chunk records")
        for path in curated_records:
            validate_instance(load_json(path), record_schema)
        validate_instance(
            load_json(ROOT / "examples" / "from-zero" / "curated" / "semantic-review.json"),
            load_json(ROOT / "contracts" / "semantic-review.v2.schema.json"),
        )
        for template in ("assets/distilled-chunk-template.json", "assets/source-map-template.json"):
            value = load_json(ROOT / template)
            if value.get("contract_version") != CONTRACT_VERSION:
                raise ContractError("invalid_template", f"template version mismatch: {template}")
        validate_instance(
            load_json(ROOT / "assets" / "semantic-review-template.json"),
            load_json(ROOT / "contracts" / "semantic-review.v2.schema.json"),
        )
        validate_instance(
            load_json(ROOT / "assets" / "query-gold-template.json"),
            load_json(ROOT / "contracts" / "query-gold.v2.schema.json"),
        )
        check_frontmatter()
        check_diagram()
        check_version_and_license_alignment()
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        if isinstance(exc, ContractError):
            print(f"FAIL {exc.code}: {exc.message}", file=sys.stderr)
        else:
            print(f"FAIL validation: {exc}", file=sys.stderr)
        return 1

    concept_exit = check_concept_continuity()
    if concept_exit:
        print("FAIL conceptual-continuity gate", file=sys.stderr)
        return 1
    test_exit = run_lifecycle_tests()
    if test_exit:
        print("FAIL lifecycle regression suite", file=sys.stderr)
        return 1
    readiness_exit = run_readiness_tests()
    if readiness_exit:
        print("FAIL real-material readiness regression suite", file=sys.stderr)
        return 1
    print(f"PASS repository validation: contract={CONTRACT_VERSION} schemas={len(schemas)} curated_records={len(curated_records)} lifecycle_cases={len(fixtures['cases'])} readiness_cases=4")
    print("PASS source intake, ordered resume, semantic-review gate, artifact-derived build, trial metrics, sparse load plan, and mandatory sweep")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
